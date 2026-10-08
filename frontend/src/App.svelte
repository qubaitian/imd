<script>
  import { readResponse, workspaceDirectory, workspaceUrl } from './api.js';
  import { onMount } from 'svelte';
  import MarkdownView from './MarkdownView.svelte';
  import { DocumentSession } from './session.svelte.js';
  import { mergeDocument, prepareOutput } from './document.js';
  import Icon from './Icon.svelte';
  import { renderMarkdown } from './markdown.js';
  import { copyDocumentReference } from './reference.js';

  let documents = $state([]);
  let active = $state(null);
  let query = $state('');
  let view = $state('preview');
  let error = $state('');
  let loading = $state(true);
  let saving = $state(false);
  let referenceStatus = $state('');
  let openRequest = 0;
  const drafts = new Map();
  const sessions = new Map();
  const timers = new Map();
  const pendingSaves = new Map();
  let session = $derived(active ? sessions.get(active.path) : null);
  let statuses = $derived(Object.fromEntries(renderMarkdown(active?.content || '').blocks.map((block, index) => [index, session?.runs[block.id] || {}])));
  let rendered = $derived(renderMarkdown(active?.content || '', statuses, session?.connected || false));
  let dirty = $derived(active && active.content !== active.saved);
  let filtered = $derived(documents.filter((path) => path.toLowerCase().includes(query.toLowerCase())));

  async function request(url, options) {
    const response = await fetch(workspaceUrl(url), options);
    return readResponse(response);
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
      referenceStatus = '';
      drafts.set(path, active);
      if (!sessions.has(path)) {
        const draft = active;
        sessions.set(path, new DocumentSession(path, (remote) => applyDocument(draft, remote), (message) => error = message));
      }
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

  function applyDocument(document, remote) {
    if (document.revision === remote.revision) return;
    try {
      if (remote.content === document.savingContent) {
        document.saved = remote.content;
        document.revision = remote.revision;
        if (document.content !== document.saved) scheduleSave(document);
        return;
      }
      document.content = mergeDocument(document.content, document.saved, remote.content);
      document.saved = remote.content;
      document.revision = remote.revision;
      document.conflict = false;
      if (document.content !== document.saved) scheduleSave(document);
    } catch (failure) {
      document.conflict = true;
      error = failure.message;
    }
  }

  function scheduleSave(document = active) {
    if (!document) return;
    clearTimeout(timers.get(document.path));
    timers.set(document.path, setTimeout(() => save(document), 700));
  }

  async function save(document = active) {
    if (!document) return;
    clearTimeout(timers.get(document.path));
    if (pendingSaves.has(document.path)) {
      await pendingSaves.get(document.path);
      if (document.content !== document.saved && !document.conflict) return save(document);
      return;
    }
    if (document.content === document.saved || document.conflict) return;
    saving = true;
    const task = (async () => {
      const content = document.content;
      const revision = document.revision;
      document.savingContent = content;
      try {
        const saved = await request('/api/document', {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: document.path, content, revision }),
        });
        if (document.revision === revision) {
          document.revision = saved.revision;
          document.saved = saved.content;
        }
      } catch (failure) {
        if (document.revision === revision || document.conflict) {
          document.conflict = true;
          error = failure.message;
        }
      } finally {
        document.savingContent = undefined;
      }
    })();
    pendingSaves.set(document.path, task);
    await task;
    pendingSaves.delete(document.path);
    saving = pendingSaves.size > 0;
    if (document.content !== document.saved && !document.conflict) scheduleSave(document);
  }

  async function runBlock(event) {
    const button = event.target.closest?.('button[data-block]');
    if (!button || button.disabled || !session?.connected) return;
    const index = Number(button.dataset.block);
    const block = rendered.blocks[index];
    if (!block) return;
    const document = active;
    const connection = session;
    try {
      await save(document);
      if (document.conflict) return;
      const prepared = prepareOutput(document.content, index, crypto.randomUUID().replaceAll('-', '').slice(0, 12));
      document.content = prepared.content;
      if (!connection.run(document, prepared.id)) {
        error = 'The session is disconnected. Your changes are kept.';
        scheduleSave(document);
      }
    } catch (failure) {
      error = failure.message;
    }
  }

  function keydown(event) {
    if (event.target?.closest?.('.xterm')) return;
    if ((event.metaKey || event.ctrlKey) && event.key === 's') {
      event.preventDefault();
      save();
    }
  }

  async function copyReference(event) {
    const document = active;
    try {
      const reference = await copyDocumentReference(event, workspaceDirectory(), document.path);
      if (reference && active === document) referenceStatus = `Copied ${reference}`;
    } catch (failure) {
      referenceStatus = '';
      error = failure.message;
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
      if (documents.includes('imd.md')) await open('imd.md');
      loading = false;
    })();
    return () => {
      for (const timer of timers.values()) clearTimeout(timer);
      for (const connection of sessions.values()) connection.close();
    };
  });
</script>

<svelte:window onkeydown={keydown} onbeforeunload={beforeUnload} />

<div class="app-shell">
  <aside class="sidebar">
    <a class="brand" href={location.pathname} aria-label="IMD home"><span class="brand-mark">i<span>m</span>d<span class="brand-dot">.</span></span><span class="brand-caption">INTERACTIVE MARKDOWN</span></a>
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
          <button class="session-reset" onclick={() => session?.reset()} disabled={!session?.connected} title="Clear the document session"><Icon name="reset" size={14} /> Reset session</button>
          <button class="save-button" onclick={() => save()} disabled={!dirty || saving}><Icon name="save" size={15} />{saving ? 'Saving…' : 'Save'}</button>
        </div>
      </div>
      <div class="document-body" class:split={view === 'split'}>
        {#if view !== 'preview'}
          <div class="editor-pane"><div class="pane-label">MARKDOWN <span>{active.content.split('\n').length} lines</span></div><textarea bind:value={active.content} oninput={() => { referenceStatus = ''; scheduleSave(); }} onkeydown={copyReference} spellcheck="false" aria-label="Markdown editor" title="Select text and press Cmd+L to copy a document reference."></textarea></div>
        {/if}
        {#if view !== 'edit'}
          <div class="preview-pane"><div class="preview-meta"><span class="eyebrow">DOCUMENT PREVIEW</span><span class="block-count">{rendered.blocks.length} executable {rendered.blocks.length === 1 ? 'block' : 'blocks'}</span></div>
            {#key active.path}<MarkdownView {rendered} {session} onrun={runBlock} />{/key}
            <div class="preview-end"><span></span><Icon name="file" size={13} /><span></span></div>
          </div>
        {/if}
      </div>
      <div class="session-footer"><span class:online={session?.connected} class="state-dot"></span><span>{session?.state || 'connecting'}</span><span class="session-directory">{session?.cwd || ''}</span><span class="reference-status" role="status" title={referenceStatus}>{referenceStatus || 'Changes and output save automatically'}</span></div>
    {:else}
      <div class="empty-state"><span class="empty-mark">imd.</span><h1>{loading ? 'Opening your workspace…' : 'Start with a Markdown file.'}</h1><p>Open a document from the sidebar.</p><p>Use a fenced code block marked <code>xonsh</code>, <code>shell</code>, <code>sh</code>, <code>py</code>, or <code>python</code> to run code.</p><p>Use an <code>agent</code> block to submit a prompt after configuring agent commands.</p></div>
    {/if}
  </main>
</div>
