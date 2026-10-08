import { describe, expect, it, vi } from 'vitest';
import { copyDocumentReference } from './reference.js';

function key(content, start, end, changes = {}) {
  return {
    key: 'l', metaKey: true, ctrlKey: false, altKey: false, shiftKey: false,
    repeat: false, isComposing: false,
    currentTarget: { value: content, selectionStart: start, selectionEnd: end },
    preventDefault: vi.fn(),
    ...changes,
  };
}

describe('Document reference', () => {
  it.each([
    ['first\nsecond\nthird', 0, 18, '1-3'],
    ['first\nsecond\nthird', 6, 9, '2-2'],
    ['first\nsecond\nthird', 0, 13, '1-2'],
    ['first\nsecond\nthird', 5, 6, '1-1'],
    ['first\n\nthird\n', 6, 7, '2-2'],
    ['😀标题\n第二行\n末行', 5, 8, '2-2'],
    ['first\r\nsecond\r\nthird', 7, 15, '2-2'],
  ])('copies source lines for a selection', async (content, start, end, lines) => {
    const event = key(content, start, end);
    const clipboard = { writeText: vi.fn().mockResolvedValue(undefined) };
    const reference = await copyDocumentReference(event, '/Users/me/notes 空格/', 'sub/imd.md', clipboard);
    expect(reference).toBe(`@/Users/me/notes 空格/sub/imd.md:${lines}`);
    expect(clipboard.writeText).toHaveBeenCalledExactlyOnceWith(reference);
    expect(event.preventDefault).toHaveBeenCalledOnce();
  });

  it('joins a document path at the filesystem root', async () => {
    const clipboard = { writeText: vi.fn().mockResolvedValue(undefined) };
    expect(await copyDocumentReference(key('note', 0, 4), '/', 'imd.md', clipboard))
      .toBe('@/imd.md:1-1');
  });

  it.each([
    { key: 's' }, { metaKey: false, ctrlKey: true }, { shiftKey: true },
    { altKey: true }, { ctrlKey: true }, { repeat: true }, { isComposing: true },
    { currentTarget: { value: 'note', selectionStart: 2, selectionEnd: 2 } },
  ])('leaves other shortcuts and empty selections alone', async (changes) => {
    const event = key('note', 0, 4, changes);
    const clipboard = { writeText: vi.fn() };
    expect(await copyDocumentReference(event, '/notes', 'imd.md', clipboard)).toBeNull();
    expect(clipboard.writeText).not.toHaveBeenCalled();
    expect(event.preventDefault).not.toHaveBeenCalled();
  });

  it('reports a clipboard failure without changing the selection', async () => {
    const event = key('note', 0, 4);
    const clipboard = { writeText: vi.fn().mockRejectedValue(new Error('denied')) };
    await expect(copyDocumentReference(event, '/notes', 'imd.md', clipboard))
      .rejects.toThrow('Cannot copy the document reference. Allow clipboard access and try again.');
    expect(event.preventDefault).toHaveBeenCalledOnce();
    expect(event.currentTarget.selectionStart).toBe(0);
    expect(event.currentTarget.selectionEnd).toBe(4);
  });

  it('reports unavailable clipboard access', async () => {
    await expect(copyDocumentReference(key('note', 0, 4), '/notes', 'imd.md', null))
      .rejects.toThrow('Cannot copy the document reference. Allow clipboard access and try again.');
  });
});
