// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { flushSync, mount, unmount } from 'svelte';
import MarkdownView from './MarkdownView.svelte';
import App from './App.svelte';
import { renderMarkdown } from './markdown.js';

vi.mock('./session.svelte.js', () => ({
  DocumentSession: class {
    connected = true;
    state = 'ready';
    cwd = '/notes';
    runs = {};
    close() {}
  },
}));
vi.mock('./Output.svelte', () => ({ default: () => {} }));

let component;

afterEach(async () => {
  if (component) await unmount(component);
  document.body.replaceChildren();
  vi.unstubAllGlobals();
});

describe('code block editor in the preview', () => {
  it('shows session information beside Reset session without a header or Save button', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url) => ({
      ok: true,
      json: async () => url.startsWith('/api/documents')
        ? { documents: ['imd.md'] }
        : { path: 'imd.md', content: '# Notes', revision: '1' },
    })));
    flushSync(() => component = mount(App, { target: document.body }));
    await vi.waitFor(() => expect(document.querySelector('.document-toolbar')).not.toBeNull());
    expect(document.querySelector('main > header')).toBeNull();
    expect([...document.querySelectorAll('button')].some((button) => button.textContent.trim() === 'Save')).toBe(false);
    const reset = [...document.querySelectorAll('button')].find((button) => button.textContent.includes('Reset session'));
    const status = reset.nextElementSibling;
    expect(status.textContent).toContain('ready');
    expect(status.textContent).toContain('/notes');
    expect(status.textContent).toContain('Changes and output save automatically');
    expect(document.querySelector('.document-body').nextElementSibling).toBeNull();
  });

  it.each(['Preview', 'Split'])('edits code in the full app in %s view', async (view) => {
    vi.stubGlobal('fetch', vi.fn(async (url) => ({
      ok: true,
      json: async () => url.startsWith('/api/documents')
        ? { documents: ['imd.md'] }
        : { path: 'imd.md', content: '```js\nold\n```', revision: '1' },
    })));
    flushSync(() => component = mount(App, { target: document.body }));
    await vi.waitFor(() => expect(document.querySelector('.code-block code')).not.toBeNull());
    flushSync(() => [...document.querySelectorAll('button')].find((button) => button.textContent === view).click());
    flushSync(() => document.querySelector('.code-block code').click());
    const editor = document.querySelector('.code-block-editor');
    expect(editor).not.toBeNull();
    flushSync(() => {
      editor.value = 'new\n';
      editor.dispatchEvent(new Event('input', { bubbles: true }));
    });
    expect(document.querySelector('[role="alert"]')).toBeNull();
    expect(document.querySelector('.save-state').textContent).toBe('Unsaved');
    expect(document.querySelector('.code-block-editor')).toBe(editor);
    if (view === 'Split') expect(document.querySelector('[aria-label="Markdown editor"]').value).toContain('new');
  });

  it.each([
    '# Heading\n\n```js\nold\n```',
    '> ```js\n> old\n> ```',
    '- ```js\n  old\n  ```',
    '```js\nfirst\n```\n\n```js\nold\n```',
  ])('keeps code clickable after changing Markdown structure: %s', async (content) => {
    vi.stubGlobal('fetch', vi.fn(async (url) => ({
      ok: true,
      json: async () => url.startsWith('/api/documents')
        ? { documents: ['imd.md'] }
        : { path: 'imd.md', content: '```js\nold\n```', revision: '1' },
    })));
    flushSync(() => component = mount(App, { target: document.body }));
    await vi.waitFor(() => expect(document.querySelector('.code-block code')).not.toBeNull());
    flushSync(() => [...document.querySelectorAll('button')].find((button) => button.textContent === 'Split').click());
    flushSync(() => {
      const editor = document.querySelector('[aria-label="Markdown editor"]');
      editor.value = content;
      editor.dispatchEvent(new Event('input', { bubbles: true }));
    });
    flushSync(() => document.querySelector('.code-block code').click());
    expect(document.querySelector('.code-block-editor')).not.toBeNull();
  });

  it('opens the editor when the code body is clicked and reports edits', () => {
    const onchange = vi.fn();
    const rendered = renderMarkdown('```js\nold\n```');
    flushSync(() => {
      component = mount(MarkdownView, {
        target: document.body,
        props: { rendered, session: {}, onrun: vi.fn(), oncodechange: onchange },
      });
    });
    const body = document.querySelector('.code-block code');
    expect(body).not.toBeNull();
    flushSync(() => body.click());
    const editor = document.querySelector('textarea');
    expect(editor).not.toBeNull();
    expect(document.activeElement).toBe(editor);
    expect(editor.value).toBe('old\n');
    flushSync(() => {
      editor.value = 'new\n';
      editor.dispatchEvent(new Event('input', { bubbles: true }));
    });
    expect(onchange).toHaveBeenCalledWith(rendered.editableBlocks[0], 'new\n');
  });
});


describe('add buttons in the full app', () => {
  it.each(['Preview', 'Split'].flatMap((view) => ['xonsh', 'markdown', 'agent'].map((kind) => [view, kind])))('adds and focuses %s %s content', async (view, kind) => {
    vi.stubGlobal('fetch', vi.fn(async (url) => ({
      ok: true,
      json: async () => url.startsWith('/api/documents')
        ? { documents: ['imd.md'] }
        : { path: 'imd.md', content: '```xonsh\necho old\n```\n\n```agent\nold prompt\n```', revision: '1' },
    })));
    flushSync(() => component = mount(App, { target: document.body }));
    await vi.waitFor(() => expect(document.querySelector('.run-button')).not.toBeNull());
    flushSync(() => [...document.querySelectorAll('button')].find((button) => button.textContent === view).click());
    const button = document.querySelector(`[data-add="${kind}"]`);
    expect(button).not.toBeNull();
    flushSync(() => button.click());
    await vi.waitFor(() => {
      flushSync();
      const editor = document.querySelector(kind === 'markdown' ? '[aria-label="Markdown editor"]' : '.code-block-editor');
      expect(editor).not.toBeNull();
      expect(document.activeElement).toBe(editor);
      if (kind === 'markdown') {
        expect(editor.value.slice(editor.selectionStart, editor.selectionEnd)).toBe('Write Markdown here.');
        expect(editor.value).not.toContain('```markdown');
      } else expect(editor.value).toBe('');
    });
    const editor = document.activeElement;
    flushSync(() => {
      editor.value = kind === 'markdown' ? editor.value.replace('Write Markdown here.', '# New note') : 'new content\n';
      editor.dispatchEvent(new Event('input', { bubbles: true }));
    });
    flushSync(() => [...document.querySelectorAll('button')].find((button) => button.textContent === 'Split').click());
    const source = document.querySelector('[aria-label="Markdown editor"]').value;
    expect(source).toContain(kind === 'markdown' ? '# New note' : 'new content');
    expect(source).toContain('old prompt');
    expect(source).toContain('echo old');
    expect(document.querySelector('.save-state').textContent).toBe('Unsaved');
    expect(document.querySelector('[role="alert"]')).toBeNull();
  });
});


describe('sticky save conflict', () => {
  function conflictFetch() {
    let current = { path: 'imd.md', content: 'original\n', revision: '1' };
    let conflicted = false;
    const puts = [];
    const fetch = vi.fn(async (url, options) => {
      if (String(url).startsWith('/api/documents')) {
        return { ok: true, json: async () => ({ documents: ['imd.md'] }) };
      }
      if (options?.method === 'PUT') {
        const body = JSON.parse(options.body);
        puts.push(body);
        if (body.revision !== current.revision) {
          return { ok: false, status: 409, json: async () => ({ detail: 'The document changed on disk. Reopen it before saving.' }) };
        }
        if (!conflicted) {
          conflicted = true;
          current = { path: 'imd.md', content: 'from disk\n', revision: '2' };
          return { ok: false, status: 409, json: async () => ({ detail: 'The document changed on disk. Reopen it before saving.' }) };
        }
        current = { path: 'imd.md', content: body.content, revision: '3' };
        return { ok: true, json: async () => current };
      }
      return { ok: true, json: async () => current };
    });
    return { fetch, puts, current: () => current };
  }

  async function edit(value) {
    flushSync(() => [...document.querySelectorAll('button')].find((button) => button.textContent === 'Edit').click());
    const editor = document.querySelector('[aria-label="Markdown editor"]');
    flushSync(() => {
      editor.value = value;
      editor.dispatchEvent(new Event('input', { bubbles: true }));
    });
    editor.dispatchEvent(new KeyboardEvent('keydown', { key: 's', metaKey: true, bubbles: true }));
    await vi.waitFor(() => expect(document.querySelector('[role="alert"]')).not.toBeNull());
    return editor;
  }

  it('keeps unsaved edits and can retry the save with Cmd+S after a conflict', async () => {
    const api = conflictFetch();
    vi.stubGlobal('fetch', api.fetch);
    flushSync(() => component = mount(App, { target: document.body }));
    await vi.waitFor(() => expect(document.querySelector('.document-toolbar')).not.toBeNull());
    const editor = await edit('mine\n');
    expect(editor.value).toBe('mine\n');
    expect(api.puts).toHaveLength(1);
    expect(api.puts[0]).toMatchObject({ content: 'mine\n', revision: '1' });
    editor.dispatchEvent(new KeyboardEvent('keydown', { key: 's', metaKey: true, bubbles: true }));
    await vi.waitFor(() => expect(api.puts).toHaveLength(2));
    expect(editor.value).toBe('mine\n');
    expect(api.puts[1]).toMatchObject({ content: 'mine\n', revision: '2' });
    expect(api.current().content).toBe('mine\n');
    expect(document.querySelector('[role="alert"]')).toBeNull();
    expect(document.querySelector('.save-state').textContent).toBe('Saved');
  });

  it('saves the original content when it is restored after a conflict', async () => {
    const api = conflictFetch();
    vi.stubGlobal('fetch', api.fetch);
    flushSync(() => component = mount(App, { target: document.body }));
    await vi.waitFor(() => expect(document.querySelector('.document-toolbar')).not.toBeNull());
    const editor = await edit('mine\n');
    flushSync(() => {
      editor.value = 'original\n';
      editor.dispatchEvent(new Event('input', { bubbles: true }));
    });
    expect(document.querySelector('.save-state').textContent).toBe('Unsaved');
    const retry = [...document.querySelectorAll('button')].find((button) => button.textContent === 'Retry save');
    flushSync(() => retry.click());
    await vi.waitFor(() => expect(api.puts).toHaveLength(2));
    expect(api.puts[1]).toMatchObject({ content: 'original\n', revision: '2' });
    expect(api.current().content).toBe(editor.value);
    expect(document.querySelector('[role="alert"]')).toBeNull();
    expect(document.querySelector('.save-state').textContent).toBe('Saved');
  });

  it('resolves a conflict without writing when the editor matches the content on disk', async () => {
    const api = conflictFetch();
    vi.stubGlobal('fetch', api.fetch);
    flushSync(() => component = mount(App, { target: document.body }));
    await vi.waitFor(() => expect(document.querySelector('.document-toolbar')).not.toBeNull());
    const editor = await edit('mine\n');
    flushSync(() => {
      editor.value = 'from disk\n';
      editor.dispatchEvent(new Event('input', { bubbles: true }));
    });
    editor.dispatchEvent(new KeyboardEvent('keydown', { key: 's', metaKey: true, bubbles: true }));
    await vi.waitFor(() => expect(document.querySelector('[role="alert"]')).toBeNull());
    expect(api.puts).toHaveLength(1);
    expect(api.current().content).toBe(editor.value);
    expect(document.querySelector('.save-state').textContent).toBe('Saved');
  });

  it('reloads the server copy without discarding edits until reload is chosen', async () => {
    const api = conflictFetch();
    vi.stubGlobal('fetch', api.fetch);
    flushSync(() => component = mount(App, { target: document.body }));
    await vi.waitFor(() => expect(document.querySelector('.document-toolbar')).not.toBeNull());
    const editor = await edit('mine\n');
    expect(editor.value).toBe('mine\n');
    const reload = [...document.querySelectorAll('button')].find((button) => button.textContent === 'Reload');
    expect(reload).toBeTruthy();
    flushSync(() => reload.click());
    await vi.waitFor(() => expect(editor.value).toBe('from disk\n'));
    expect(api.puts).toHaveLength(1);
    expect(document.querySelector('[role="alert"]')).toBeNull();
    flushSync(() => {
      editor.value = 'after reload\n';
      editor.dispatchEvent(new Event('input', { bubbles: true }));
    });
    editor.dispatchEvent(new KeyboardEvent('keydown', { key: 's', metaKey: true, bubbles: true }));
    await vi.waitFor(() => expect(api.puts).toHaveLength(2));
    expect(api.puts[1]).toMatchObject({ content: 'after reload\n', revision: '2' });
    expect(editor.value).toBe('after reload\n');
  });
});
