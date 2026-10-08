import { analyzeDocument } from './document.js';

export function insertBlock(content, index, kind) {
  if (!['xonsh', 'markdown', 'agent'].includes(kind)) throw new Error('The block type is invalid.');
  const block = analyzeDocument(content).blocks[index];
  if (!block) throw new Error('The code block is missing.');
  const lines = content.match(/[^\n]*\n|[^\n]+$/g) || [];
  const closing = lines[block.map[1] - 1]?.trimEnd().match(/^(.*?)(`{3,}|~{3,})\s*$/);
  if (block.map[1] <= block.map[0] + 1 || !closing || closing[2][0] !== block.token.markup[0] || closing[2].length < block.token.markup.length) {
    throw new Error('Close the code block before adding content.');
  }
  const boundary = block.outputMap?.[1] ?? block.map[1];
  const newline = lines[block.map[0]].endsWith('\r\n') ? '\r\n' : '\n';
  const prefix = closing[1];
  const before = lines.slice(0, boundary).join('');
  const separator = (before.endsWith('\n') ? '' : newline) + prefix + newline;
  const text = kind === 'markdown' ? 'Write Markdown here.' : `\`\`\`${kind}`;
  const body = kind === 'markdown' ? prefix + text + newline : `${prefix}${text}${newline}${prefix}\`\`\`${newline}`;
  const start = before.length + separator.length + prefix.length;
  return {
    content: before + separator + body + prefix + newline + lines.slice(boundary).join(''),
    line: (before + separator).split('\n').length - 1,
    start,
    end: start + text.length,
  };
}
