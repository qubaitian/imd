import { describe, expect, it } from 'vitest';
import { renderMarkdown } from './markdown.js';

describe('executable blocks', () => {
  it('disables Run until the document session is connected', () => {
    const source = '```py\nprint(42)\n```';
    expect(renderMarkdown(source, {}, false).html).toContain('disabled');
    expect(renderMarkdown(source, {}, true).html).not.toContain('disabled');
  });

  it('accepts every agreed label and preserves the exact code', () => {
    for (const language of ['xonsh', 'shell', 'sh', 'py', 'python', 'agent', 'js', 'txt', 'custom', '']) {
      const { html, blocks } = renderMarkdown(`\`\`\`${language}\ncd child\n$VALUE = 'kept'\n\`\`\``);
      expect(blocks.map(({ language, code }) => ({ language, code }))).toEqual([{ language: language || 'xonsh', code: "cd child\n$VALUE = 'kept'\n" }]);
      expect(html).toContain('data-block="0"');
      expect(html).toContain('Run');
    }
  });

  it('offers Run for arbitrary labels and nested fences', () => {
    const { html, blocks } = renderMarkdown('```js\nalert(1)\n```\n\n> ```py\n> print(42)\n> ```');
    expect(blocks.map(({ language, code }) => ({ language, code }))).toEqual([{ language: 'js', code: 'alert(1)\n' }, { language: 'py', code: 'print(42)\n' }]);
    expect(html.match(/data-block=/g)).toHaveLength(2);
  });

  it('escapes document HTML and code without changing executable content', () => {
    const { html, blocks } = renderMarkdown('<script>alert(1)</script>\n\n```python\nprint("<img src=x onerror=alert(1)>")\n```');
    expect(html).not.toContain('<script>');
    expect(html).not.toContain('<img');
    expect(blocks[0].code).toContain('<img src=x onerror=alert(1)>');
  });
});


it('keeps add buttons available offline and during a run', () => {
  const source = '```xonsh\necho old\n```\n<!-- abc123 -->\n```txt\n```\n\n```js\nexample\n```';
  const html = renderMarkdown(source, { abc123: { status: 'running' } }, false).html;
  const additions = [...html.matchAll(/<button class="add-button"[^>]*>/g)].map((match) => match[0]);
  expect(additions).toHaveLength(6);
  for (const block of [0, 1]) {
    expect(additions.filter((button) => button.includes(`data-after="${block}"`))).toHaveLength(3);
  }
  expect(additions.every((button) => !button.includes('disabled'))).toBe(true);
});
