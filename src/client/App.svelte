<script lang="ts">
  import DOMPurify from 'dompurify';
  import { marked } from 'marked';
  import { onMount } from 'svelte';
  import {
    addCodeBlock,
    deleteBlock,
    deleteOutput,
    findCodeBlocks,
    setCode,
    setOutput,
    splitSegments,
  } from '../shared/blocks.ts';
  import CodeBlock from './CodeBlock.svelte';
  import { connectShell, type RunResult } from './shell.ts';

  type View = 'editor' | 'preview';

  let filePath = $state('');
  let content = $state('');
  let savedContent = $state('');
  let loading = $state(true);
  let agents = $state<string[]>([]);
  let running = $state<{ index: number; runId: string }>();
  let focusIndex = $state<number>();
  let view = $state<View>(localStorage.getItem('imd:view') === 'editor' ? 'editor' : 'preview');
  let textarea: HTMLTextAreaElement;

  const token = window.location.hash.slice(1);
  const headers = { Authorization: `Bearer ${token}` };
  const shell = connectShell(token);
  const status = $derived(loading ? 'Loading…' : content === savedContent ? 'Saved' : 'Unsaved changes');
  const render = (markdown: string) => DOMPurify.sanitize(marked.parse(markdown, { async: false }) as string);

  onMount(async () => {
    void fetch('/api/agents', { headers })
      .then(response => (response.ok ? response.json() : []))
      .then(names => (agents = names));
    const response = await fetch('/api/document', { headers });
    if (!response.ok) throw new Error(`Could not open the document (${response.status}).`);
    const document: { path: string; content: string } = await response.json();
    filePath = document.path;
    content = savedContent = document.content.replace(/\r\n?/g, '\n');
    loading = false;
  });

  function show(next: View) {
    view = next;
    localStorage.setItem('imd:view', next);
    void save();
  }

  async function save() {
    const next = content;
    if (next === savedContent) return;
    const response = await fetch('/api/document', {
      method: 'PUT',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: next }),
    });
    if (response.ok) savedContent = next;
  }

  function editInTextarea(next: string) {
    const previous = textarea.value;
    let start = 0;
    while (start < previous.length && start < next.length && previous[start] === next[start]) start++;
    let endPrevious = previous.length;
    let endNext = next.length;
    while (endPrevious > start && endNext > start && previous[endPrevious - 1] === next[endNext - 1]) {
      endPrevious--;
      endNext--;
    }
    const [selectionStart, selectionEnd] = [textarea.selectionStart, textarea.selectionEnd];
    const shift = (at: number) => (at <= start ? at : Math.max(start, at + endNext - endPrevious));
    textarea.focus();
    textarea.setSelectionRange(start, endPrevious);
    const text = next.slice(start, endNext);
    document.execCommand(text === '' ? 'delete' : 'insertText', false, text);
    if (textarea.value !== next) content = next;
    textarea.setSelectionRange(shift(selectionStart), shift(selectionEnd));
  }

  function edit(next: string) {
    if (view === 'editor') editInTextarea(next);
    else content = next;
    void save();
  }

  function outputText({ output, exitCode, reason }: RunResult) {
    const note = {
      done: '',
      failed: `[exit ${exitCode}]`,
      stopped: '[stopped]',
      timeout: '[timeout: no output for 60 s]',
    }[reason];
    return note ? `${output}\n${note}` : output;
  }

  async function run(index: number) {
    const block = findCodeBlocks(content, agents)[index];
    if (!block || running) return;
    void save();
    const runId = crypto.randomUUID();
    running = { index, runId };
    const result = await shell.run(runId, block.info, block.code);
    const blocks = findCodeBlocks(content, agents);
    const target = blocks[index]?.code === block.code ? index : blocks.findIndex(other => other.code === block.code);
    running = undefined;
    if (target >= 0) edit(setOutput(content, target, outputText(result), agents));
  }

  function runAtCursor(event: KeyboardEvent) {
    if (event.key !== 'Enter' || !event.shiftKey) return;
    const at = textarea.selectionStart;
    const index = findCodeBlocks(content, agents).findIndex(block => block.start <= at && at <= block.end);
    if (index < 0) return;
    event.preventDefault();
    show('preview');
    void run(index);
  }

  function addBlock() {
    content = addCodeBlock(content);
    focusIndex = findCodeBlocks(content, agents).length - 1;
    void save();
  }
</script>

<div class="app-shell">
  <header class="topbar">
    <div class="identity">
      <span class="mark">IMD</span><span class="divider"></span><span class="file-path" title={filePath}
        >{filePath || 'Opening document…'}</span
      >
    </div>
    <div class="view-toggle" role="group" aria-label="View">
      <button type="button" aria-pressed={view === 'editor'} onclick={() => show('editor')}>EDITOR</button>
      <button type="button" aria-pressed={view === 'preview'} onclick={() => show('preview')}>PREVIEW</button>
    </div>
    <span class="status" aria-live="polite">{status}</span>
  </header>

  <main class="workspace">
    <section class="pane" aria-label="Markdown editor" hidden={view !== 'editor'}>
      <textarea
        bind:this={textarea}
        bind:value={content}
        onblur={save}
        onkeydown={runAtCursor}
        disabled={loading}
        spellcheck="true"
        aria-label="Markdown text"
        placeholder="Start writing Markdown…"></textarea>
    </section>
    <section class="pane" aria-label="Markdown preview" hidden={view !== 'preview'}>
      <article class="markdown-body">
        {#snippet renderSegments(parent: number | undefined)}
          {#each splitSegments(content, agents, parent) as segment, i (segment.kind === 'code' ? `code-${segment.index}` : `markdown-${i}`)}
            {#if segment.kind === 'code'}
              <CodeBlock
                block={segment.block}
                runId={running?.index === segment.index ? running.runId : undefined}
                busy={running !== undefined}
                focus={focusIndex === segment.index}
                {shell}
                onCode={code => (content = setCode(content, segment.index, code, agents))}
                onSave={save}
                onRun={() => run(segment.index)}
                onStop={shell.stop}
                onDelete={() => edit(deleteBlock(content, segment.index, agents))}
                onDeleteOutput={() => edit(deleteOutput(content, segment.index, agents))}
                onFocused={() => (focusIndex = undefined)}
              >
                {@render renderSegments(segment.index)}
              </CodeBlock>
            {:else}
              <!-- eslint-disable-next-line svelte/no-at-html-tags -- preview is sanitized by DOMPurify -->
              {@html render(segment.text)}
            {/if}
          {/each}
        {/snippet}
        {@render renderSegments(undefined)}
        <button type="button" class="block-button add-block" onclick={addBlock} disabled={loading}>+ code block</button>
      </article>
    </section>
  </main>
</div>
