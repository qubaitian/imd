import { describe, expect, it } from 'vitest';
import { renderMarkdown } from './markdown.js';

describe('executable blocks', () => {
  it('disables Run until the document session is connected', () => {
    const source = '```py\nprint(42)\n```';
    expect(renderMarkdown(source, {}, false).html).toContain('disabled');
    expect(renderMarkdown(source, {}, true).html).not.toContain('disabled');
  });

  it('accepts every agreed label and preserves the exact code', () => {
    for (const language of ['xonsh', 'shell', 'sh', 'py', 'python']) {
      const { html, blocks } = renderMarkdown(`\`\`\`${language}\ncd child\n$VALUE = 'kept'\n\`\`\``);
      expect(blocks.map(({ language, code }) => ({ language, code }))).toEqual([{ language, code: "cd child\n$VALUE = 'kept'\n" }]);
      expect(html).toContain('data-block="0"');
      expect(html).toContain('Run');
    }
  });

  it('keeps other blocks as examples and handles nested fences', () => {
    const { html, blocks } = renderMarkdown('```js\nalert(1)\n```\n\n> ```py\n> print(42)\n> ```');
    expect(blocks.map(({ language, code }) => ({ language, code }))).toEqual([{ language: 'py', code: 'print(42)\n' }]);
    expect(html.match(/data-block=/g)).toHaveLength(1);
  });

  it('escapes document HTML and code without changing executable content', () => {
    const { html, blocks } = renderMarkdown('<script>alert(1)</script>\n\n```python\nprint("<img src=x onerror=alert(1)>")\n```');
    expect(html).not.toContain('<script>');
    expect(html).not.toContain('<img');
    expect(blocks[0].code).toContain('<img src=x onerror=alert(1)>');
  });
});
