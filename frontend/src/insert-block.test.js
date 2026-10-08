import { describe, expect, it } from 'vitest';
import { insertBlock } from './insert-block.js';
import { analyzeDocument } from './document.js';

describe('insert block', () => {
  it.each(['xonsh', 'agent'])('adds an empty %s block after saved output', (kind) => {
    const source = '```xonsh\necho old\n```\n\n<!-- abc123 -->\n```txt\nold output\n```\n\n# Next\n';
    const result = insertBlock(source, 0, kind);
    const blocks = analyzeDocument(result.content).blocks;
    expect(blocks.map((block) => block.language)).toEqual(['xonsh', kind]);
    expect(blocks[0].output).toBe('old output\n');
    expect(blocks[1].code).toBe('');
    expect(blocks[1].map[0]).toBe(result.line);
    expect(result.content.indexOf(`\`\`\`${kind}`, 1)).toBeLessThan(result.content.indexOf('# Next'));
  });

  it('adds ordinary Markdown with a selected placeholder', () => {
    const result = insertBlock('```xonsh\n```', 0, 'markdown');
    expect(result.content.slice(result.start, result.end)).toBe('Write Markdown here.');
    expect(analyzeDocument(result.content).blocks).toHaveLength(1);
    expect(result.content).not.toContain('```markdown');
  });

  it.each(['> ', '  '])('keeps the container prefix %s', (prefix) => {
    const opening = prefix === '  ' ? '- ' : prefix;
    const source = `${opening}\`\`\`xonsh\n${prefix}echo old\n${prefix}\`\`\`\n`;
    const result = insertBlock(source, 0, 'agent');
    expect(result.content).toContain(`${prefix}\`\`\`agent\n${prefix}\`\`\``);
    expect(analyzeDocument(result.content).blocks).toHaveLength(2);
  });

  it('preserves CRLF and rejects unfinished blocks', () => {
    expect(insertBlock('```xonsh\r\n```\r\n', 0, 'agent').content).not.toMatch(/(?<!\r)\n/);
    expect(() => insertBlock('```xonsh\necho old', 0, 'agent')).toThrow('Close');
  });
});
