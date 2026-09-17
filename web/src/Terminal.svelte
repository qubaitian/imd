<script>
  import { onMount } from "svelte";
  import { Terminal } from "@xterm/xterm";
  import "@xterm/xterm/css/xterm.css";
  import { terminalLinks } from "./links.js";

  let { prefix = "", data = "", disabled = false, onData, onOpenUrl } = $props();
  let host;
  let terminal = $state.raw(null);
  let written = "";
  let previousPrefix = "";

  onMount(() => {
    const instance = new Terminal({
      cols: 100,
      rows: 24,
      convertEol: true,
      fontSize: 12,
      fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace',
      lineHeight: 1.4,
      scrollback: 10000,
      cursorBlink: true,
      theme: {
        background: "#ffffff",
        foreground: "#455764",
        cursor: "#3174b8",
        selectionBackground: "#c9dff4",
      },
    });
    instance.open(host);
    instance.registerLinkProvider({
      provideLinks(line, callback) {
        callback(terminalLinks(instance, line, onOpenUrl));
      },
    });
    instance.textarea.setAttribute("aria-label", "Terminal input");
    const subscription = instance.onData((value) => {
      if (!disabled) onData(value);
    });
    terminal = instance;
    instance.focus();
    host.scrollIntoView({ block: "nearest" });
    return () => {
      subscription.dispose();
      instance.dispose();
    };
  });

  $effect(() => {
    if (!terminal) return;
    terminal.options.disableStdin = disabled;
  });

  $effect(() => {
    if (!terminal) return;
    if (prefix !== previousPrefix || !data.startsWith(written)) {
      terminal.reset();
      written = "";
      previousPrefix = prefix;
      terminal.write(prefix);
    }
    const next = data.slice(written.length);
    written = data;
    if (next) terminal.write(next);
  });
</script>

<div class="output-body command-terminal" bind:this={host}></div>
