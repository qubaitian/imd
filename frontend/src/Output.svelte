<script>
  import { Terminal } from '@xterm/xterm';
  import { FitAddon } from '@xterm/addon-fit';
  import '@xterm/xterm/css/xterm.css';
  import Icon from './Icon.svelte';

  let { id, text, session } = $props();
  let run = $derived(session.runs[id]);
  let running = $derived(run?.status === 'running');
  let terminal = $state();
  let consumed = 0;

  function openTerminal(element) {
    const currentId = run.id;
    const term = new Terminal({
      fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace',
      fontSize: 13, lineHeight: 1.4, cursorBlink: true, screenReaderMode: true, scrollback: 5000,
      theme: { background: '#192522', foreground: '#d4dfd7', cursor: '#b9d5bd', selectionBackground: '#3f5d4e' },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(element);
    consumed = 0;
    terminal = term;
    let frame;
    const size = () => {
      fit.fit();
      session.resize(currentId, term.cols, term.rows);
    };
    size();
    element.scrollIntoView({ block: 'nearest' });
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(size);
    });
    observer.observe(element);
    const input = term.onData((data) => session.input(currentId, data));
    term.focus();
    return { destroy() { observer.disconnect(); cancelAnimationFrame(frame); input.dispose(); terminal = undefined; term.dispose(); } };
  }

  $effect(() => {
    if (terminal && running) {
      const output = run.output || '';
      if (output.length < consumed) { terminal.reset(); consumed = 0; }
      terminal.write(output.slice(consumed));
      consumed = output.length;
    }
  });
</script>

<div class="output-header"><span class="output-label">txt <span class="output-marker">{id}</span></span><span class="output-state">{run?.saveError ? 'Save failed' : run?.status === 'queued' ? 'Queued' : running ? 'Running' : run?.status || 'Output'}</span>{#if running}<button class="output-stop" onclick={() => session.send({ type: 'interrupt' })}><Icon name="stop" size={12} /> Stop</button>{/if}</div>
{#if running}
  <div class="inline-terminal"><div class="terminal-host" use:openTerminal></div></div>
  <div class="output-help">Type here to interact · Arrow keys and Vim are supported · Ctrl+C to stop</div>
{:else}
  <pre class="output-text"><code>{run?.saveError ? run.text : text}</code></pre>
{/if}
