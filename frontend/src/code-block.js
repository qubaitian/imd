import { analyzeDocument } from './document.js';

export function replaceCodeBlock(content, block, code) {
  const { tokens, outputs } = analyzeDocument(content);
  const token = tokens.find((candidate) => candidate.type === 'fence' && candidate.map[0] === block.map[0]);
  if (!token || outputs.has(token) || token.content !== block.code || token.info !== block.info) {
    throw new Error('The code block changed. Your edits are kept.');
  }
  const lines = content.match(/[^\n]*\n|[^\n]+$/g) || [];
  const start = token.map[0];
  const end = token.map[1];
  const opening = lines[start].match(/^(.*?)(`{3,}|~{3,})([^\r\n]*)(\r?\n)?$/);
  const [, prefix, originalFence, info] = opening;
  const character = originalFence[0];
  const closing = lines[end - 1]?.trimEnd().match(/^(.*?)(`{3,}|~{3,})\s*$/);
  const closed = end > start + 1 && closing && closing[2][0] === character && closing[2].length >= originalFence.length;
  const bodyPrefix = closed ? closing[1] : prefix.replace(/(?:[-+*]|\d+[.)])\s/g, (marker) => ' '.repeat(marker.length));
  const newline = lines[start].endsWith('\r\n') ? '\r\n' : '\n';
  const normalized = code.replace(/\r\n/g, '\n');
  const runs = [...normalized.matchAll(character === '`' ? /`+/g : /~+/g)];
  const fence = character.repeat(Math.max(originalFence.length, ...runs.map((match) => match[0].length + 1)));
  const body = normalized ? normalized.replace(/\n$/, '').split('\n').map((line) => bodyPrefix + line + newline).join('') : '';
  const suffix = closed ? bodyPrefix + fence + (lines[end - 1].endsWith('\n') ? newline : '') : '';
  return lines.slice(0, start).join('') + prefix + fence + info + newline + body + suffix + lines.slice(end).join('');
}
