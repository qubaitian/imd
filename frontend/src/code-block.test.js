import { describe, expect, it } from 'vitest';
import { replaceCodeBlock } from './code-block.js';
import { renderMarkdown } from './markdown.js';

describe('code block editing', () => {
  it('replaces only the selected body and preserves its output', () => {
    const source = '# Note\n\n```agent\nold\n```\n\n<!-- abc123 -->\n```txt\nresult\n```\n';
    const block = renderMarkdown(source).editableBlocks[0];
    expect(replaceCodeBlock(source, block, 'new\n')).toBe(source.replace('old\n', 'new\n'));
    expect(renderMarkdown(source).editableBlocks).toHaveLength(1);
  });

  it('includes examples but not output blocks and disables active runs', () => {
    const source = '```js\nexample\n```\n```py\nrun\n```';
    const rendered = renderMarkdown(source, { 0: { status: 'running' } });
    expect(rendered.editableBlocks.map(({ editable }) => editable)).toEqual([true, false]);
    expect(rendered.html).toContain('data-code-slot="0"');
    expect(rendered.html).toContain('data-code-slot="1"');
  });

  it('preserves quote and list indentation', () => {
    for (const source of ['> ```py\n> old\n> ```\n', '- ```py\n  old\n  ```\n', '  ```py\n  old\n  ```\n']) {
      const next = replaceCodeBlock(source, renderMarkdown(source).editableBlocks[0], 'first\nsecond');
      expect(renderMarkdown(next).editableBlocks[0].code).toBe('first\nsecond\n');
    }
  });

  it('grows the fence when edited code contains a closing fence', () => {
    const source = '~~~js\nold\n~~~';
    const next = replaceCodeBlock(source, renderMarkdown(source).editableBlocks[0], '~~~\nnew');
    expect(next).toBe('~~~~js\n~~~\nnew\n~~~~');
    expect(renderMarkdown(next).editableBlocks).toHaveLength(1);
  });

  it('supports empty bodies and an unclosed fence', () => {
    const source = '```py\nold';
    expect(replaceCodeBlock(source, renderMarkdown(source).editableBlocks[0], '')).toBe('```py\n');
  });

  it('rejects stale blocks and output block edits', () => {
    const source = '```py\nold\n```';
    const block = renderMarkdown(source).editableBlocks[0];
    expect(() => replaceCodeBlock(source.replace('old', 'other'), block, 'new')).toThrow('changed');
    const output = { ...block, map: [5, 8], code: 'result\n' };
    expect(() => replaceCodeBlock(source + '\n<!-- abc123 -->\n```txt\nresult\n```', output, 'new')).toThrow();
  });
});
