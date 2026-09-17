<script>
  import { onMount } from "svelte";
  import { followLinks, linkedText } from "./links.js";

  let { base, path, token, onOpenLink } = $props();
  let source = $state("");
  let error = $state("");

  async function openLink(value) {
    error = "";
    try { await onOpenLink(value); }
    catch (failure) { error = failure.message; }
  }

  onMount(async () => {
    try {
      const response = await fetch(`${base}/api/document`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "The file does not open.");
      source = data.source;
    } catch (failure) { error = failure.message; }
  });
</script>

<section class="app-shell text-pane" aria-label={path}>
  <header class="topbar">
    <div class="breadcrumb"><span>{path.split("/").pop()}</span></div>
    <span class="readonly-label">Read-only</span>
  </header>
  {#if error}<div class="error-banner" role="alert">{error}</div>{/if}
  <div class="document-scroll" use:followLinks={openLink}>
    <pre class="text-file">{@html linkedText(source)}</pre>
  </div>
  <footer class="statusbar"><span title={path}>{path}</span></footer>
</section>
