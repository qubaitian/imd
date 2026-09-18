<script>
  import { onMount, tick } from "svelte";
  import MarkdownIt from "markdown-it";
  import taskLists from "markdown-it-task-lists";
  import hljs from "highlight.js/lib/core";
  import python from "highlight.js/lib/languages/python";
  import bash from "highlight.js/lib/languages/bash";
  import Editor from "./Editor.svelte";
  import Terminal from "./Terminal.svelte";
  import { editBlock, blockAtCursor, deleteBlock, adjacentOutput } from "./document.js";
  import { followLinks, linkedHtml } from "./links.js";

  hljs.registerLanguage("python", python);
  hljs.registerLanguage("bash", bash);
  const markdown = new MarkdownIt({ html: false, linkify: true }).use(
    taskLists,
  );
  markdown.linkify.set({ fuzzyLink: false });
  const renderImage = markdown.renderer.rules.image;
  markdown.renderer.rules.image = (tokens, index, options, env, renderer) => {
    const image = tokens[index];
    const source = image.attrGet("src") || "";
    if (source && !/^(?:[a-z]+:|\/\/|#)/i.test(source)) {
      image.attrSet("src", `${base}/api/assets/${source.replace(/^\.?\//, "")}`);
    }
    return renderImage(tokens, index, options, env, renderer);
  };
  let { base, token, paneId, onOpenLink } = $props();
  let pane;

  let doc = $state(null);
  let mode = $state("preview");
  let active = $state(-1);
  let draft = $state("");
  let sourceDraft = $state("");
  let status = $state("Opening");
  let error = $state("");
  let recovery = $state("");
  let running = $state(-1);
  let runId = $state("");
  let terminalData = $state("");
  let terminalInputQueue = Promise.resolve();
  let interrupted = $state(false);
  let stopping = $state(false);
  let controlError = $state("");
  let linkError = $state("");
  let cursor = 0;
  let queue = Promise.resolve();
  let suppressBlur = false;

  const markdownEnvironment = $derived.by(() => {
    const environment = {};
    markdown.parse(doc?.source || "", environment);
    return environment;
  });

  const blockChildren = $derived.by(() => {
    const children = new Map();
    for (const [index, block] of (doc?.blocks || []).entries()) {
      if (!children.has(block.parent)) children.set(block.parent, []);
      children.get(block.parent).push({ block, index });
    }
    return children;
  });
  const replacedOutput = $derived(
    running >= 0 ? adjacentOutput(doc.source, doc.blocks, running) : null,
  );

  function render(raw) {
    return linkedHtml(markdown.render(raw, { ...markdownEnvironment }));
  }
  function highlight(code, language) {
    return linkedHtml(
      hljs.highlight(code, {
        language: language === "python" ? "python" : "bash",
      }).value,
    );
  }
  function currentSource() {
    if (!doc) return "";
    if (mode === "source") return sourceDraft;
    return active >= 0 && doc.blocks[active]
      ? editBlock(doc.source, doc.blocks[active], draft)
      : doc.source;
  }
  async function api(path, method = "GET", body = undefined, onEvent = null, signal = undefined) {
    const response = await fetch(`${base}/api/${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: onEvent ? "application/x-ndjson" : "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
    if (!response.ok) {
      const data = await response.json();
      const detail = data.detail;
      const failure = new Error(
        typeof detail === "string" ? detail : detail?.message || "The request failed.",
      );
      failure.source = detail?.source;
      throw failure;
    }
    let data;
    if (onEvent) {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      try {
        while (true) {
          const { value, done } = await reader.read();
          buffer += decoder.decode(value, { stream: !done });
          const lines = buffer.split("\n");
          buffer = lines.pop();
          if (done && buffer) lines.push(buffer);
          for (const line of lines) {
            if (!line.trim()) continue;
            const event = JSON.parse(line);
            if (event.type === "error") {
              const failure = new Error(
                typeof event.detail === "string" ? event.detail : event.detail.message,
              );
              failure.source = event.detail?.source;
              throw failure;
            }
            if (event.type === "done") data = event.document;
            else onEvent(event);
          }
          if (done) break;
        }
      } finally {
        reader.releaseLock();
      }
      if (!data) throw new Error("The execution connection closed. Reload the document to check the saved output.");
    } else data = await response.json();
    if (data.blocks)
      data.blocks = data.blocks.map((block) => ({
        ...block,
        start: block.start_utf16,
        end: block.end_utf16,
      }));
    return data;
  }
  async function openLink(value) {
    linkError = "";
    try {
      if (running >= 0)
        throw new Error("Wait for execution to finish before opening a link.");
      await enqueue(saveNow);
      await onOpenLink(value);
    } catch (failure) {
      linkError = failure.message;
    }
  }
  function enqueue(action) {
    queue = queue.then(action);
    return queue;
  }
  function accept(data, source) {
    const unchanged = currentSource() === source;
    doc = data;
    if (unchanged) {
      sourceDraft = data.source;
      if (active >= 0 && data.blocks[active])
        draft =
          data.blocks[active].kind === "markdown"
            ? data.blocks[active].raw
            : data.blocks[active].code;
    }
    status = unchanged ? "Saved" : "Unsaved";
    error = "";
    recovery = "";
  }
  async function saveNow() {
    if (!doc) return;
    const source = currentSource();
    if (source === doc.source) return;
    status = "Saving";
    accept(
      await api("document", "PUT", { source, revision: doc.revision }),
      source,
    );
  }
  function save() {
    if (suppressBlur || running >= 0) return;
    return enqueue(saveNow);
  }
  function changed(value) {
    if (mode === "source") sourceDraft = value;
    else draft = value;
    status = "Unsaved";
  }
  function activate(block, index) {
    if (running >= 0 || active === index) return;
    const delta = currentSource().length - doc.source.length;
    const start =
      block.start +
      (active >= 0 && doc.blocks[active].start < block.start ? delta : 0);
    enqueue(async () => {
      await saveNow();
      active = doc.blocks.findIndex((item) => item.start === start);
      const selected = doc.blocks[active];
      if (selected)
        draft = selected.kind === "markdown" ? selected.raw : selected.code;
    });
  }
  function switchMode(next) {
    if (running >= 0 || next === mode) return;
    enqueue(async () => {
      await saveNow();
      suppressBlur = true;
      active = -1;
      sourceDraft = doc.source;
      mode = next;
      queueMicrotask(() => {
        suppressBlur = false;
      });
    });
  }
  function removeBlock(index) {
    if (running >= 0) return;
    const selected = doc.blocks[index];
    const shift = active >= 0 && doc.blocks[active].start < selected.start
      ? currentSource().length - doc.source.length
      : 0;
    const targetStart = selected.start + shift;
    enqueue(async () => {
      const source = currentSource();
      const parsed = await api("parse", "POST", { source });
      const target = parsed.blocks.findIndex((block) => block.start === targetStart);
      const next = deleteBlock(source, parsed.blocks, target);
      if (next === source) return;
      status = "Saving";
      const data = await api("document", "PUT", { source: next, revision: doc.revision });
      suppressBlur = true;
      active = -1;
      draft = "";
      doc = data;
      sourceDraft = data.source;
      status = "Saved";
      error = "";
      recovery = "";
      await tick();
      suppressBlur = false;
    });
  }
  function run(index = active, position = cursor) {
    if (running >= 0) return;
    const selected = mode === "preview" ? doc.blocks[index] : null;
    const shift =
      active >= 0 && selected && doc.blocks[active].start < selected.start
        ? currentSource().length - doc.source.length
        : 0;
    const targetStart = selected ? selected.start + shift : -1;
    const keepEditor = mode === "preview" && active === index;
    enqueue(async () => {
      const source = currentSource();
      const parsed = await api("parse", "POST", { source });
      if (mode === "source") index = blockAtCursor(parsed.blocks, position);
      else
        index = parsed.blocks.findIndex((block) => block.start === targetStart);
      if (index < 0 || parsed.blocks[index]?.kind !== "code") {
        await saveNow();
        return;
      }
      doc = { ...doc, source, blocks: parsed.blocks };
      sourceDraft = source;
      active = keepEditor ? index : -1;
      draft = keepEditor ? parsed.blocks[index].code : "";
      running = index;
      runId = "";
      terminalData = "";
      interrupted = false;
      stopping = false;
      controlError = "";
      status = "Running";
      error = "";
      try {
        const data = await api("execute", "POST", {
          source,
          revision: doc.revision,
          block: index,
        }, (event) => {
          if (event.type === "start") runId = event.id;
          else if (event.type === "data") terminalData += event.text;
        });
        accept(data, source);
        if (mode === "preview") {
          active = keepEditor ? index : -1;
          draft = keepEditor ? data.blocks[index].code : "";
        }
      } catch (failure) {
        error = failure.message;
      } finally {
        running = -1;
        runId = "";
        interrupted = false;
        stopping = false;
        if (status === "Running") status = "Saved";
      }
    });
  }
  function sendTerminalInput(value) {
    if (!runId || stopping) return;
    const execution = runId;
    terminalInputQueue = terminalInputQueue.then(async () => {
      if (runId !== execution) return;
      await api(`execute/${execution}/input`, "POST", { value });
    });
  }
  async function stop() {
    if (!runId || stopping) return;
    controlError = "";
    if (!interrupted) {
      interrupted = true;
      await api(`execute/${runId}/stop`, "POST", {});
      return;
    }
    stopping = true;
    await api(`execute/${runId}/kill`, "POST", {});
  }
  function append(kind) {
    enqueue(async () => {
      await saveNow();
      const ending =
        doc.source && !doc.source.endsWith("\n\n")
          ? doc.source.endsWith("\n")
            ? "\n"
            : "\n\n"
          : "";
      const source =
        doc.source + ending + (kind === "code" ? "```python\n\n```\n" : "\n");
      const data = await api("document", "PUT", {
        source,
        revision: doc.revision,
      });
      doc = data;
      if (kind === "code") {
        mode = "preview";
        active = data.blocks.length - 1;
        draft = data.blocks[active].code;
      } else {
        mode = "source";
        active = -1;
        sourceDraft = source;
      }
      status = "Saved";
    });
  }
  function download() {
    const url = URL.createObjectURL(
      new Blob([recovery || currentSource()], {
        type: "text/markdown;charset=utf-8",
      }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `recovery-${doc?.name || "IMD.md"}`;
    link.click();
    URL.revokeObjectURL(url);
  }
  function keepFocus(event) {
    event.preventDefault();
  }
  function blockKey(event, block, index) {
    if (event.key === "Enter" && event.shiftKey && block.kind === "code") {
      event.preventDefault();
      run(index);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      activate(block, index);
    }
  }

  onMount(() => {
    api("document")
      .then((data) => {
        doc = data;
        sourceDraft = data.source;
        status = "Saved";
      });
    const blur = () => save();
    const beforeUnload = (event) => {
      if (doc && (currentSource() !== doc.source || running >= 0 || error)) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    const visibility = () => {
      if (document.visibilityState === "hidden") save();
    };
    window.addEventListener("blur", blur);
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      window.removeEventListener("blur", blur);
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("visibilitychange", visibility);
    };
  });
</script>

{#snippet trashIcon()}
  <svg viewBox="0 0 24 24" aria-hidden="true"
    ><path d="M4 7h16M9 7V4h6v3M6 7v13h12V7M10 11v5M14 11v5" /></svg
  >
{/snippet}

{#snippet executionOutput()}
  <section class="notebook-block output-block live-output">
    <div class="output-label">
      <span>↳</span> OUT
      <button class="run-button delete-button" aria-label="Delete output block" disabled
        >{@render trashIcon()}Del</button
      >
      <button class="run-button" onclick={stop} disabled={!runId || stopping}>
        {stopping ? "Killing…" : interrupted ? "Kill" : "Stop"}
      </button>
    </div>
    {#key runId}
      <Terminal
        data={terminalData}
        disabled={stopping}
        onData={sendTerminalInput}
        onOpenLink={openLink}
      />
    {/key}
    {#if controlError}<div role="alert">{controlError}</div>{/if}
  </section>
{/snippet}

{#snippet documentBlocks(parent)}
  {#each blockChildren.get(parent) || [] as { block, index } (index)}
    <section
      hidden={block === replacedOutput}
      id={`${paneId}-block-${block.start}`}
      class="notebook-block"
      class:active={active === index}
      class:code-block={block.kind === "code"}
      class:output-block={block.kind === "output"}
    >
      {#if block.kind === "code"}
        <div class="code-header">
          <div>
            <span class="code-symbol"
              >{block.language === "python" ? "{ }" : ">_"}</span
            ><span>{block.language || "text"}</span>
          </div>
          <div>
            <button
              class="run-button"
              aria-label="Run current block"
              title="Run current block · Shift + Enter"
              onpointerdown={keepFocus}
              onclick={() => run(index)}
              disabled={running >= 0}
              ><span class:spinner={running === index}
                >{running === index ? "" : "▷"}</span
              >{running === index ? "Running" : "Run"}</button
            >
            <button
              class="run-button delete-button"
              aria-label="Delete code block"
              title="Delete code block and its output"
              onpointerdown={keepFocus}
              onclick={() => removeBlock(index)}
              disabled={running >= 0}>{@render trashIcon()}Del</button
            >
          </div>
        </div>
        {#if active === index}<Editor
            value={draft}
            language={block.language}
            onChange={changed}
            onRun={() => run(index)}
            onBlur={save}
            readonly={running >= 0}
          />{:else}<div
            class="code-preview"
            role="button"
            tabindex="0"
            aria-label={`Edit the ${block.language || "text"} code block`}
            onclick={() => activate(block, index)}
            onkeydown={(event) => blockKey(event, block, index)}
          >
            <pre><code
                >{@html highlight(
                  block.code,
                  block.language,
                )}</code
              ></pre>
          </div>{/if}
      {:else if block.kind === "output"}
        <div class="output-label">
          <span>↳</span> OUT<span class="output-caption">output</span>
          <button
            class="run-button delete-button"
            aria-label="Delete output block"
            title="Delete output block"
            onpointerdown={keepFocus}
            onclick={() => removeBlock(index)}
            disabled={running >= 0}>{@render trashIcon()}Del</button
          >
        </div>
        <div class="output-body markdown-output">
          {#if blockChildren.has(index)}
            {@render documentBlocks(index)}
          {:else}
            <span>(no output)</span>
          {/if}
        </div>
      {:else if active === index}
        <div class="markdown-edit">
          <div class="edit-label">
            MARKDOWN <span>Saves on blur</span>
          </div>
          <Editor
            value={draft}
            language="markdown"
            onChange={changed}
            onRun={() => save()}
            onBlur={save}
            readonly={running >= 0}
          />
        </div>
      {:else}
        <div
          class={block.parent === null ? "prose-block" : "output-prose"}
          role="button"
          tabindex="0"
          aria-label="Edit Markdown block"
          onclick={(event) => {
            if (!event.target.closest("a")) activate(block, index);
          }}
          onkeydown={(event) => blockKey(event, block, index)}
        >
          {@html render(block.raw)}
        </div>
      {/if}
    </section>
    {#if running === index}{@render executionOutput()}{/if}
  {/each}
{/snippet}

<div class="app-shell" bind:this={pane}>
  <header class="topbar">
    <div class="breadcrumb">
      <svg viewBox="0 0 24 24" aria-hidden="true"
        ><path d="M5 3h9l5 5v13H5zM14 3v6h5" /></svg
      ><span title={doc?.name}>{doc?.name || "Markdown"}</span><span class="local-badge"
        >Local</span
      >
    </div>
    <div class="view-tabs" aria-label="Document view">
      <button
        class:selected={mode === "preview"}
        onpointerdown={keepFocus}
        onclick={() => switchMode("preview")}
        disabled={running >= 0}
        ><svg viewBox="0 0 24 24" aria-hidden="true"
          ><path
            d="M3 5h7a3 3 0 0 1 3 3v13a4 4 0 0 0-4-3H3zM13 8a3 3 0 0 1 3-3h5v13h-4a4 4 0 0 0-4 3"
          /></svg
        >Document</button
      >
      <button
        class:selected={mode === "source"}
        onpointerdown={keepFocus}
        onclick={() => switchMode("source")}
        disabled={running >= 0}
        ><svg viewBox="0 0 24 24" aria-hidden="true"
          ><path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18" /></svg
        >Source</button
      >
    </div>
    <div
      class="save-state"
      class:unsaved={status === "Unsaved"}
      class:working={["Opening", "Saving", "Running"].includes(status)}
    >
      <span class="status-dot"></span><span
        data-testid="save-status"
        aria-live="polite">{status}</span
      >
    </div>
  </header>

  <div class="workspace">
    <main>
      {#if error}<div class="error-banner" role="alert">
          <span>{error}</span>{#if doc}<button onclick={download}
              >Download current content</button
            >{/if}
        </div>{/if}

      {#if linkError}<div class="error-banner" role="alert">{linkError}</div>{/if}

      <div class="document-scroll" use:followLinks={openLink}>
        {#if doc}
          {#if mode === "source"}
            <section class="source-panel">
              <div class="source-title">
                <span>{doc.name}</span><span>Markdown</span>
              </div>
              <Editor
                value={sourceDraft}
                language="markdown"
                onChange={changed}
                onRun={(position) => {
                  cursor = position;
                  run(-1, position);
                }}
                onBlur={save}
                readonly={running >= 0}
              />
            </section>
            {#if running >= 0}{@render executionOutput()}{/if}
          {:else if !doc.blocks.length}
            <section class="empty-state">
              <div class="empty-mark">M<span>↓</span></div>
              <div class="eyebrow">One file. Many ideas.</div>
              <h1>Start with text.</h1>
              <p>
                Write Markdown. Run code.<br
                />Results stay next to your text.
              </p>
              <div>
                <button
                  class="primary-button"
                  onpointerdown={keepFocus}
                  onclick={() => append("markdown")}
                  >Write Markdown <span>↗</span></button
                ><button
                  class="secondary-button"
                  onpointerdown={keepFocus}
                  onclick={() => append("code")}>Add a code block</button
                >
              </div>
              <div class="empty-hint">
                <kbd>Enter</kbd> adds a line<span>·</span><kbd>Shift + Enter</kbd> runs
              </div>
            </section>
          {:else}
            <article class="notebook markdown-body">
              {@render documentBlocks(null)}
            </article>
            <div class="append-row">
              <span></span><button
                onpointerdown={keepFocus}
                onclick={() => append("markdown")}
                disabled={running >= 0}>＋ Text</button
              ><button
                onpointerdown={keepFocus}
                onclick={() => append("code")}
                disabled={running >= 0}>＋ Code</button
              ><span></span>
            </div>
          {/if}
        {:else if !error}<div class="loading-state">Opening the document…</div>{/if}
      </div>
      <div class="statusbar">
        <span title={doc?.path}>{doc?.path || "IMD"}</span><span
          >Markdown<span class="meta-dot">·</span>Shell</span
        >
      </div>
    </main>
  </div>
</div>
