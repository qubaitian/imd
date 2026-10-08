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
