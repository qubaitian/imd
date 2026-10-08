import { describe, expect, it } from 'vitest';
import { analyzeDocument, prepareOutput, replaceOutput, mergeDocument } from './document.js';
import { renderMarkdown } from './markdown.js';

const source = '# Note\n\n```py\nprint(42)\n```\n\nKeep this paragraph.\n';

describe('Markdown output blocks', () => {
  it('adds a marker and txt fence directly after the selected block', () => {
    const prepared = prepareOutput(source, 0, 'abc123');
    expect(prepared.id).toBe('abc123');
    expect(prepared.content).toContain('```\n\n<!-- abc123 -->\n```txt\n```');
    expect(analyzeDocument(prepared.content).blocks[0].id).toBe('abc123');
    expect(prepared.content).toContain('Keep this paragraph.');
  });

  it('keeps the same marker and replaces output when running again', () => {
    const first = prepareOutput(source, 0, 'abc123');
    const saved = replaceOutput(first.content, 'abc123', 'old\n');
    const rerun = prepareOutput(saved, 0, 'def456');
    expect(rerun.id).toBe('abc123');
    expect(rerun.content).not.toContain('old\n');
    expect(rerun.content.match(/<!-- abc123 -->/g)).toHaveLength(1);
  });

  it('hides only output markers and creates an inline output slot', () => {
    const marked = prepareOutput(source, 0, 'abc123').content;
    const rendered = renderMarkdown(marked);
    expect(rendered.html).not.toContain('&lt;!-- abc123');
    expect(rendered.html).toContain('data-output-slot="abc123"');
    expect(rendered.outputs[0]).toMatchObject({ id: 'abc123', text: '' });
    expect(renderMarkdown('<!-- a normal note -->').html).toContain('&lt;!--');
  });

  it('preserves nested fences and output containing backticks', () => {
    const nested = '> ```sh\n> echo hello\n> ```\n';
    const marked = prepareOutput(nested, 0, 'abc123').content;
    const saved = replaceOutput(marked, 'abc123', '```\nhello\n');
    expect(saved).toContain('> ````txt\n> ```\n> hello\n> ````');
    expect(analyzeDocument(saved).blocks[0].output).toBe('```\nhello\n');
  });

  it('merges output into unsaved text without overwriting the text', () => {
    const before = prepareOutput(source, 0, 'abc123').content;
    const local = before.replace('Keep this paragraph.', 'My unsaved paragraph.');
    const remote = replaceOutput(before, 'abc123', '42\n');
    const merged = mergeDocument(local, before, remote);
    expect(merged).toContain('My unsaved paragraph.');
    expect(merged).toContain('```txt\n42\n```');
  });

  it('rejects conflicting text edits rather than overwriting either edit', () => {
    expect(() => mergeDocument(source + 'Local.\n', source, source + 'Remote.\n')).toThrow('changed');
  });
});
