import { marked, type Token } from 'marked';

export interface OutputBlock {
  start: number;
  end: number;
  id: string;
  text: string;
}

export interface CodeBlock {
  start: number;
  end: number;
  info: string;
  code: string;
  markdown: boolean;
  output?: OutputBlock;
}

export type Segment = { kind: 'markdown'; text: string } | { kind: 'code'; index: number; block: CodeBlock };

const beginPattern = /^<!-- imd:output:begin (\S+) -->/;
const endPattern = /^<!-- imd:output:end (\S+) -->/;

interface Located {
  token: Token;
  start: number;
  end: number;
}

function locate(md: string): Located[] {
  const located: Located[] = [];
  let cursor = 0;
  for (const token of marked.lexer(md)) {
    const start = md.startsWith(token.raw, cursor) ? cursor : md.indexOf(token.raw, cursor);
    if (start < 0) continue;
    cursor = start + token.raw.length;
    if (token.type !== 'space') located.push({ token, start, end: start + token.raw.trimEnd().length });
  }
  return located;
}

const markerId = (item: Located | undefined, pattern: RegExp) =>
  item?.token.type === 'html' ? item.token.raw.match(pattern)?.[1] : undefined;

export function findCodeBlocks(md: string, agents: string[] = []): CodeBlock[] {
  const items = locate(md);
  const blocks: CodeBlock[] = [];
  for (let i = 0; i < items.length; i++) {
    const { token, start, end } = items[i];
    const beginId = markerId(items[i], beginPattern);
    if (beginId !== undefined) {
      const close = items.findIndex((item, j) => j > i && markerId(item, endPattern) === beginId);
      if (close > i) i = close;
      continue;
    }
    if (token.type !== 'code' || token.codeBlockStyle === 'indented') continue;
    const info = (token.lang ?? '').trim();
    const [name, ...words] = info.split(/\s+/);
    const block: CodeBlock = {
      start,
      end,
      info,
      code: token.text,
      markdown: words.includes('md') || agents.includes(name),
    };
    const next = items[i + 1];
    const id = markerId(next, beginPattern);
    const close = items.findIndex((item, j) => j > i + 1 && markerId(item, endPattern) === id);
    if (id !== undefined && close > 0 && md.slice(end, next.start).trim() === '') {
      const inner = items.slice(i + 2, close);
      const text =
        !block.markdown && inner.length === 1 && inner[0].token.type === 'code'
          ? inner[0].token.text
          : md.slice(next.start + next.token.raw.length, items[close].start).trim();
      block.output = { start: next.start, end: items[close].end, id, text };
      i = close;
    }
    blocks.push(block);
  }
  return blocks;
}

function newId() {
  return Array.from(crypto.getRandomValues(new Uint8Array(3)), byte => byte.toString(16).padStart(2, '0')).join('');
}

function formatOutput(text: string, id: string, markdown: boolean) {
  const body = text.replace(/^\s*\n|\s+$/g, '');
  const inner = markdown
    ? `\n${body}\n`
    : (() => {
        const fence = '`'.repeat(Math.max(3, ...Array.from(body.matchAll(/`+/g), run => run[0].length + 1)));
        return `${fence}txt\n${body}\n${fence}`;
      })();
  return `<!-- imd:output:begin ${id} -->\n${inner}\n<!-- imd:output:end ${id} -->`;
}

export function setOutput(md: string, index: number, text: string, agents: string[] = []) {
  const block = findCodeBlocks(md, agents)[index];
  if (!block) return md;
  const output = formatOutput(text, block.output?.id ?? newId(), block.markdown);
  if (block.output) return md.slice(0, block.output.start) + output + md.slice(block.output.end);
  return `${md.slice(0, block.end)}\n\n${output}${md.slice(block.end)}`;
}

export function deleteOutput(md: string, index: number) {
  const block = findCodeBlocks(md)[index];
  if (!block?.output) return md;
  return md.slice(0, block.end) + md.slice(block.output.end);
}

export function deleteBlock(md: string, index: number) {
  const block = findCodeBlocks(md)[index];
  if (!block) return md;
  const rest = md.slice(block.output?.end ?? block.end).replace(/^\n+/, '');
  return rest === '' ? md.slice(0, block.start).replace(/\n+$/, '\n') : md.slice(0, block.start) + rest;
}

export function setCode(md: string, index: number, code: string) {
  const block = findCodeBlocks(md)[index];
  if (!block) return md;
  const lineEnd = md.indexOf('\n', block.start);
  const [, indent, marks, rest] = md
    .slice(block.start, lineEnd < 0 ? block.end : lineEnd)
    .match(/^( *)(`{3,}|~{3,})(.*)$/)!;
  const runs = Array.from(code.matchAll(new RegExp(`^ *(\\${marks[0]}{3,})`, 'gm')), run => run[1].length + 1);
  const fence = marks[0].repeat(Math.max(marks.length, ...runs));
  const body = code === '' ? '' : `${code}\n`;
  return `${md.slice(0, block.start)}${indent}${fence}${rest}\n${body}${indent}${fence}${md.slice(block.end)}`;
}

export function addCodeBlock(md: string) {
  const before = md.replace(/\n+$/, '');
  return `${before}${before === '' ? '' : '\n\n'}\`\`\`sh\n\`\`\`\n`;
}

export function splitSegments(md: string, agents: string[] = []): Segment[] {
  const segments: Segment[] = [];
  let cursor = 0;
  findCodeBlocks(md, agents).forEach((block, index) => {
    if (block.start > cursor) segments.push({ kind: 'markdown', text: md.slice(cursor, block.start) });
    segments.push({ kind: 'code', index, block });
    cursor = block.output?.end ?? block.end;
  });
  if (cursor < md.length) segments.push({ kind: 'markdown', text: md.slice(cursor) });
  return segments;
}
