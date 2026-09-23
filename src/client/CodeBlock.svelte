<script lang="ts">
  import { FitAddon } from '@xterm/addon-fit';
  import { Terminal } from '@xterm/xterm';
  import '@xterm/xterm/css/xterm.css';
  import DOMPurify from 'dompurify';
  import { marked } from 'marked';
  import type { CodeBlock } from '../shared/blocks.ts';
  import type { ShellClient } from './shell.ts';

  let {
    block,
    runId,
    busy,
    focus,
    shell,
    onCode,
    onSave,
    onRun,
    onStop,
    onDelete,
    onDeleteOutput,
    onFocused,
  }: {
    block: CodeBlock;
    runId: string | undefined;
    busy: boolean;
    focus: boolean;
    shell: ShellClient;
    onCode: (code: string) => void;
    onSave: () => void;
    onRun: () => void;
    onStop: () => void;
    onDelete: () => void;
    onDeleteOutput: () => void;
    onFocused: () => void;
  } = $props();

  let codeField: HTMLTextAreaElement;

  $effect(() => {
    if (!focus) return;
    codeField.focus();
    onFocused();
  });

  function runOnShiftEnter(event: KeyboardEvent) {
    if (event.key !== 'Enter' || !event.shiftKey) return;
    event.preventDefault();
    if (!busy) onRun();
  }

  const outputHtml = $derived(
    block.markdown && block.output
      ? DOMPurify.sanitize(marked.parse(block.output.text, { async: false }) as string)
      : '',
  );

  function terminal(node: HTMLElement, id: string) {
    const term = new Terminal({
      rows: 12,
      fontSize: 13,
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
      theme: { background: '#1c2731', foreground: '#e6ecef', cursor: '#a8d7d0' },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(node);
    fit.fit();
    shell.resize(term.cols, term.rows);
    const input = term.onData(data => shell.input(data));
    const unlisten = shell.listen(id, data => term.write(data));
    term.focus();
    return {
      destroy() {
        unlisten();
        input.dispose();
        term.dispose();
      },
    };
  }
</script>

<div class="code-block">
  <div class="block-toolbar">
    <span class="block-info">{block.info || 'sh'}</span>
    {#if runId}
      <button type="button" class="block-button" onclick={onStop}>stop</button>
    {:else}
      <button type="button" class="block-button" onclick={onRun} disabled={busy} title="Shift+Enter">run</button>
    {/if}
    <button type="button" class="block-button" onclick={onDelete} disabled={!!runId}>del</button>
  </div>
  <textarea
    bind:this={codeField}
    class="block-code"
    value={block.code}
    rows={Math.max(1, block.code.split('\n').length)}
    wrap="off"
    spellcheck="false"
    readonly={!!runId}
    placeholder="Type a command, then press Shift+Enter"
    aria-label="Code block"
    oninput={event => onCode(event.currentTarget.value)}
    onkeydown={runOnShiftEnter}
    onblur={onSave}></textarea>
  {#if runId}
    <div class="block-terminal" use:terminal={runId}></div>
  {:else if block.output}
    <div class="block-output">
      <div class="block-toolbar">
        <span class="block-info">output</span>
        <button type="button" class="block-button" onclick={onDeleteOutput}>del</button>
      </div>
      {#if block.markdown}
        <!-- eslint-disable-next-line svelte/no-at-html-tags -- output is sanitized by DOMPurify -->
        <div class="output-markdown">{@html outputHtml}</div>
      {:else}
        <pre><code>{block.output.text}</code></pre>
      {/if}
    </div>
  {/if}
</div>
