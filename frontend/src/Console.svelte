<script>
  import { onMount } from 'svelte';
  import { Terminal } from '@xterm/xterm';
  import { FitAddon } from '@xterm/addon-fit';
  import '@xterm/xterm/css/xterm.css';
  import Icon from './Icon.svelte';

  let { path, connected = $bindable(false), onrun, onerror } = $props();
  let container;
  let terminal;
  let socket;
  let fit;
  let cwd = $state('');
  let state = $state('connecting');
  let resetting = $state(false);
  let disposed = false;

  function send(message) {
    if (socket?.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify(message));
    return true;
  }

  export function run(code, id) {
    const sent = send({ type: 'run', code, id });
    if (sent) terminal?.focus();
    return sent;
  }

  async function reset() {
    resetting = true;
    try {
      const response = await fetch(`/api/session/reset?path=${encodeURIComponent(path)}`, { method: 'POST' });
      if (!response.ok) throw new Error((await response.json()).detail);
      if (!disposed) onrun?.({ type: 'reset' });
    } catch (error) {
      if (!disposed) onerror?.(error.message);
    } finally {
      resetting = false;
    }
  }

  onMount(() => {
    let reconnect;
    let resizeFrame;
    terminal = new Terminal({
      fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace',
      fontSize: 12,
      lineHeight: 1.5,
      cursorBlink: true,
      screenReaderMode: true,
      scrollback: 5000,
      theme: { background: '#192522', foreground: '#d4dfd7', cursor: '#b9d5bd', selectionBackground: '#3f5d4e', black: '#192522', green: '#a7d4af' },
    });
    fit = new FitAddon();
    terminal.loadAddon(fit);
    terminal.open(container);
    fit.fit();

    function size() {
      if (disposed) return;
      fit.fit();
      send({ type: 'resize', columns: terminal.cols, rows: terminal.rows });
    }

    function connect() {
      state = 'connecting';
      socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/session?path=${encodeURIComponent(path)}`);
      socket.onmessage = ({ data }) => {
        if (disposed) return;
        const message = JSON.parse(data);
        if (message.type === 'snapshot') {
          terminal.reset();
          terminal.write(message.output);
          cwd = message.cwd;
          state = message.state;
          connected = true;
          size();
        } else if (message.type === 'output') {
          terminal.write(message.data);
        } else if (message.type === 'running') {
          state = 'running';
          onrun?.(message);
        } else if (message.type === 'done') {
          state = 'ready';
          cwd = message.cwd;
          onrun?.(message);
        } else if (message.type === 'queued') {
          onrun?.(message);
        } else if (message.type === 'error') {
          onerror?.(message.message);
          onrun?.({ ...message, status: 'error' });
        } else if (message.type === 'closed') {
          connected = false;
          state = 'closed';
        }
      };
      socket.onclose = ({ code }) => {
        if (disposed) return;
        connected = false;
        state = 'disconnected';
        if (code === 1008) {
          onerror?.('Cannot connect to this document session.');
          return;
        }
        reconnect = setTimeout(connect, 1000);
      };
    }

    const input = terminal.onData((data) => {
      if (data === '\x03') send({ type: 'interrupt' });
      else send({ type: 'input', data });
    });
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(size);
    });
    observer.observe(container);
    connect();
    return () => {
      disposed = true;
      connected = false;
      clearTimeout(reconnect);
      cancelAnimationFrame(resizeFrame);
      observer.disconnect();
      input.dispose();
      socket?.close();
      terminal.dispose();
    };
  });
</script>

<section class="console" aria-label="Document console">
  <div class="console-toolbar">
    <div class="console-title"><Icon name="terminal" size={16} /><span>Console</span><span class:busy={state === 'running'} class:online={connected} class="state-dot"></span><span class="session-state">{state}</span></div>
    <span class="console-cwd" title={cwd}>{cwd || 'Starting document session…'}</span>
    <div class="console-actions">
      <button onclick={() => send({ type: 'interrupt' })} disabled={state !== 'running'} title="Interrupt the current run (Ctrl+C)"><Icon name="stop" size={13} /> Stop</button>
      <button onclick={reset} disabled={resetting || !connected} title="Clear the directory, environment, and variables"><Icon name="reset" size={14} /> {resetting ? 'Resetting…' : 'Reset session'}</button>
    </div>
  </div>
  <div class="console-body" bind:this={container}></div>
  <div class="console-footer"><span>One document · one session</span><span>Type here when a command asks for input <span class="keycap">Ctrl C</span> to stop</span></div>
</section>
