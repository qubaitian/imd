<script lang="ts">
  import DOMPurify from 'dompurify';
  import { marked } from 'marked';
  import { onMount } from 'svelte';

  let filePath = $state('');
  let content = $state('');
  let savedContent = $state('');
  let loading = $state(true);

  const headers = { Authorization: `Bearer ${window.location.hash.slice(1)}` };
  const preview = $derived(DOMPurify.sanitize(marked.parse(content, { async: false }) as string));
  const status = $derived(loading ? 'Loading…' : content === savedContent ? 'Saved' : 'Unsaved changes');

  onMount(async () => {
    const response = await fetch('/api/document', { headers });
    if (!response.ok) throw new Error(`Could not open the document (${response.status}).`);
    const document: { path: string; content: string } = await response.json();
    filePath = document.path;
    content = savedContent = document.content;
    loading = false;
  });

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
</script>

<div class="app-shell">
  <header class="topbar">
    <div class="identity">
      <span class="mark">IMD</span><span class="divider"></span><span class="file-path" title={filePath}
        >{filePath || 'Opening document…'}</span
      >
    </div>
    <span class="status" aria-live="polite">{status}</span>
  </header>

  <main class="workspace">
    <section class="pane editor-pane" aria-label="Markdown editor">
      <div class="pane-heading"><span class="pane-label">EDITOR</span><span class="pane-hint">Markdown</span></div>
      <textarea
        bind:value={content}
        onblur={save}
        disabled={loading}
        spellcheck="true"
        aria-label="Markdown text"
        placeholder="Start writing Markdown…"></textarea>
    </section>
    <section class="pane preview-pane" aria-label="Markdown preview">
      <div class="pane-heading"><span class="pane-label">PREVIEW</span><span class="pane-hint">Live</span></div>
      <!-- eslint-disable-next-line svelte/no-at-html-tags -- preview is sanitized by DOMPurify -->
      <article class="markdown-body">{@html preview}</article>
    </section>
  </main>
</div>
