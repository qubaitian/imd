// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { flushSync, mount, unmount } from 'svelte';
import MarkdownView from './MarkdownView.svelte';
import App from './App.svelte';
import { renderMarkdown } from './markdown.js';

vi.mock('./session.svelte.js', () => ({
  DocumentSession: class {
    connected = true;
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
