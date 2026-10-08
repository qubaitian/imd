<script>
  import { onMount } from 'svelte';
  import DOMPurify from 'dompurify';
  import Console from './Console.svelte';
  import Icon from './Icon.svelte';
  import { renderMarkdown } from './markdown.js';

  let documents = $state([]);
  let active = $state(null);
  let query = $state('');
  let view = $state('preview');
  let error = $state('');
  let loading = $state(true);
  let saving = $state(false);
  let connected = $state(false);
  let statuses = $state({});
  let consoleView = $state();
  let openRequest = 0;
  const drafts = new Map();
  const runBlocks = new Map();
  let rendered = $derived(renderMarkdown(active?.content || '', statuses, connected));
  let html = $derived(DOMPurify.sanitize(rendered.html));
  let dirty = $derived(active && active.content !== active.saved);
  let filtered = $derived(documents.filter((path) => path.toLowerCase().includes(query.toLowerCase())));

  async function request(url, options) {
    const response = await fetch(url, options);
    const body = await response.json();
    if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'The request failed.');
    return body;
  }

  async function open(path) {
    if (active?.path === path) return;
    const requestId = ++openRequest;
    error = '';
    try {
      const document = drafts.get(path) || await request(`/api/document?path=${encodeURIComponent(path)}`);
      if (requestId !== openRequest) return;
      if (active) drafts.set(active.path, active);
      active = document.saved === undefined ? { ...document, saved: document.content } : document;
      statuses = {};
      runBlocks.clear();
      localStorage.setItem('imd-document', path);
    } catch (failure) {
      if (requestId === openRequest) error = failure.message;
    }
  }

  async function refresh() {
    try {
      ({ documents } = await request('/api/documents'));
    } catch (failure) {
      error = failure.message;
    }
  }

  async function save() {
    if (!active || saving) return;
    saving = true;
    error = '';
    const document = active;
    const content = document.content;
    try {
      const saved = await request('/api/document', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: document.path, content, revision: document.revision }),
      });
      document.revision = saved.revision;
      document.saved = saved.content;
    } catch (failure) {
      error = failure.message;
    } finally {
      saving = false;
    }
  }

  function runBlock(event) {
    const button = event.target.closest?.('button[data-block]');
    if (!button || button.disabled || !connected) return;
    const index = Number(button.dataset.block);
    const block = rendered.blocks[index];
    if (!block) return;
    const id = crypto.randomUUID();
    if (consoleView.run(block.code, id)) {
      runBlocks.set(id, index);
      statuses[index] = { id, status: 'queued' };
    }
  }

  function runEvent(event) {
    if (event.type === 'reset') {
      statuses = {};
      runBlocks.clear();
      return;
    }
    const index = runBlocks.get(event.id);
    if (index === undefined || statuses[index]?.id !== event.id) return;
    statuses[index] = { id: event.id, status: event.status || event.type };
    if (event.type === 'done' || event.type === 'error') runBlocks.delete(event.id);
  }

  function keydown(event) {
    if ((event.metaKey || event.ctrlKey) && event.key === 's') {
      event.preventDefault();
      save();
    }
  }

  function beforeUnload(event) {
    if (dirty || [...drafts.values()].some((document) => document.content !== document.saved)) {
      event.preventDefault();
      event.returnValue = '';
    }
  }

  onMount(() => {
    (async () => {
      await refresh();
      const previous = localStorage.getItem('imd-document');
      const first = documents.includes(previous) ? previous : documents[0];
      if (first) await open(first);
      loading = false;
    })();
  });
</script>

<svelte:window onkeydown={keydown} onbeforeunload={beforeUnload} />

<div class="app-shell">
  <aside class="sidebar">
    <a class="brand" href="/" aria-label="IMD home"><span class="brand-mark">i<span>m</span>d<span class="brand-dot">.</span></span><span class="brand-caption">INTERACTIVE MARKDOWN</span></a>
    <div class="workspace-label"><Icon name="folder" size={15} /><span>Local workspace</span><span class="local-badge">LOCAL</span></div>
    <div class="document-heading"><span>DOCUMENTS</span><button class="icon-button" onclick={refresh} title="Refresh file list"><Icon name="reset" size={14} /></button></div>
    <input class="file-search" type="search" bind:value={query} placeholder="Find a document…" aria-label="Find a document" />
    <nav class="document-list" aria-label="Documents">
      {#each filtered as path}
        <button class:active={active?.path === path} onclick={() => open(path)} title={path}><Icon name="file" size={16} /><span>{path}</span>{#if drafts.get(path)?.content !== drafts.get(path)?.saved || (active?.path === path && dirty)}<span class="draft-dot" title="Unsaved changes"></span>{/if}</button>
      {/each}
      {#if !filtered.length}<p class="no-documents">{loading ? 'Loading…' : query ? 'No matching documents.' : 'Add a .md file to the workspace, then refresh.'}</p>{/if}
    </nav>
    <div class="sidebar-footer"><span class="footer-symbol">⌘</span><p>Notes that run.<br /><span>Your files. Your session.</span></p></div>
  </aside>

  <main>
    <header class="topbar"><div class="breadcrumb">Workspace <span>/</span> <strong>{active?.path || 'Documents'}</strong></div><span class="topbar-note"><span class="small-dot"></span> Runs on your machine</span></header>
    {#if error}<div class="error-banner" role="alert"><span>{error}</span><button onclick={() => error = ''} aria-label="Dismiss error">×</button></div>{/if}
    {#if active}
      <div class="document-toolbar">
        <div class="document-title"><Icon name="file" size={21} /><h1>{active.path.split('/').pop()}</h1><span class="save-state">{dirty ? 'Unsaved' : 'Saved'}</span></div>
        <div class="document-controls">
          <div class="view-toggle" aria-label="Document view">{#each ['preview', 'split', 'edit'] as mode}<button class:selected={view === mode} onclick={() => view = mode}>{mode === 'preview' ? 'Preview' : mode === 'split' ? 'Split' : 'Edit'}</button>{/each}</div>
          <button class="save-button" onclick={save} disabled={!dirty || saving}><Icon name="save" size={15} />{saving ? 'Saving…' : 'Save'}</button>
        </div>
      </div>
      <div class="document-body" class:split={view === 'split'}>
        {#if view !== 'preview'}
          <div class="editor-pane"><div class="pane-label">MARKDOWN <span>{active.content.split('\n').length} lines</span></div><textarea bind:value={active.content} oninput={() => statuses = {}} spellcheck="false" aria-label="Markdown editor"></textarea></div>
        {/if}
        {#if view !== 'edit'}
          <div class="preview-pane"><div class="preview-meta"><span class="eyebrow">DOCUMENT PREVIEW</span><span class="block-count">{rendered.blocks.length} executable {rendered.blocks.length === 1 ? 'block' : 'blocks'}</span></div>
            <!-- Run buttons are delegated from the rendered Markdown. -->
            <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
            <article class="markdown" class:offline={!connected} onclick={runBlock}>{@html html}</article>
            <div class="preview-end"><span></span><Icon name="file" size={13} /><span></span></div>
          </div>
        {/if}
      </div>
      {#key active.path}<Console bind:this={consoleView} path={active.path} bind:connected onrun={runEvent} onerror={(message) => error = message} />{/key}
    {:else}
      <div class="empty-state"><span class="empty-mark">imd.</span><h1>{loading ? 'Opening your workspace…' : 'Start with a Markdown file.'}</h1><p>Open a document from the sidebar.</p><p>Use a fenced code block marked <code>xonsh</code>, <code>shell</code>, <code>sh</code>, <code>py</code>, or <code>python</code> to run code.</p></div>
    {/if}
  </main>
</div>
