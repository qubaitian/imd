import MarkdownIt from 'markdown-it';

const markerPattern = /^<!--\s*([a-f0-9]{6,32})\s*-->$/;

export function analyzeDocument(content) {
  const markdown = new MarkdownIt({ html: true });
  const tokens = markdown.parse(content, {});
  const blocks = [];
  const markers = new Set();
  const outputs = new Map();
  for (let index = 0; index < tokens.length; index++) {
    const token = tokens[index];
    if (token.type !== 'fence' || outputs.has(token)) continue;
    const language = token.info.trim().split(/\s+/)[0].toLowerCase() || 'xonsh';
    const marker = tokens[index + 1];
    const output = tokens[index + 2];
    const match = marker?.type === 'html_block' && marker.content.trim().match(markerPattern);
    const linked = match && output?.type === 'fence' && output.info.trim() === 'txt';
    const block = { language, code: token.content, map: token.map, token, id: linked ? match[1] : null, output: linked ? output.content : '', outputMap: linked ? output.map : null };
    if (linked) {
      markers.add(marker);
      outputs.set(output, block);
      block.markerMap = marker.map;
    }
    blocks.push(block);
  }
  return { markdown, tokens, blocks, markers, outputs };
}

function splice(content, start, end, replacement) {
  const lines = content.match(/[^\n]*\n|[^\n]+$/g) || [];
  return lines.slice(0, start).join('') + replacement + lines.slice(end).join('');
}

export function prepareOutput(content, index, id) {
  const { blocks } = analyzeDocument(content);
  const block = blocks[index];
  if (!block) throw new Error('The code block is missing.');
  if (block.id) return { id: block.id, content: replaceOutput(content, block.id, '') };
  if (!/^[a-f0-9]{6,32}$/.test(id) || blocks.some((other) => other.id === id)) throw new Error('The output marker is invalid or duplicated.');
  const lines = content.match(/[^\n]*\n|[^\n]+$/g) || [];
  const closing = lines[block.map[1] - 1]?.trimEnd().match(/^(.*?)(?:`{3,}|~{3,})\s*$/);
  if (!closing) throw new Error('Close the code fence before running it.');
  const prefix = closing[1];
  const insert = `${lines[block.map[1] - 1].endsWith('\n') ? '' : '\n'}${prefix}\n${prefix}<!-- ${id} -->\n${prefix}\`\`\`txt\n${prefix}\`\`\`\n`;
  return { id, content: splice(content, block.map[1], block.map[1], insert) };
}

export function replaceOutput(content, id, text) {
  const matches = analyzeDocument(content).blocks.filter((block) => block.id === id);
  if (matches.length !== 1) throw new Error('The output marker is missing or duplicated.');
  const block = matches[0];
  const lines = content.match(/[^\n]*\n|[^\n]+$/g) || [];
  const prefix = lines[block.outputMap[0]].match(/^(.*?)(?:`{3,}|~{3,})/)[1];
  const fence = '`'.repeat(Math.max(3, ...[...text.matchAll(/`+/g)].map((match) => match[0].length + 1)));
  const body = text ? text.replace(/\n$/, '').split('\n').map((line) => prefix + line + '\n').join('') : '';
  return splice(content, ...block.outputMap, `${prefix}${fence}txt\n${body}${prefix}${fence}\n`);
}

function bodyFingerprint(content) {
  const { tokens, markers, outputs } = analyzeDocument(content);
  return JSON.stringify(tokens.filter((token) => !markers.has(token) && !outputs.has(token)).map(({ type, tag, nesting, content, info, markup }) => ({ type, tag, nesting, content, info, markup })));
}

export function mergeDocument(local, before, remote) {
  if (local === before || local === remote) return remote;
  if (bodyFingerprint(before) !== bodyFingerprint(remote)) throw new Error('The document changed on disk. Your edits are kept.');
  let content = local;
  for (const block of analyzeDocument(remote).blocks.filter((block) => block.id)) {
    const localBlocks = analyzeDocument(content).blocks;
    let matching = localBlocks.find((candidate) => candidate.id === block.id);
    if (!matching) {
      const candidates = localBlocks.filter((candidate) => !candidate.id && candidate.code === block.code && candidate.language === block.language);
      if (candidates.length !== 1) throw new Error('The code changed. Your edits are kept.');
      content = prepareOutput(content, localBlocks.indexOf(candidates[0]), block.id).content;
      matching = candidates[0];
    }
    if (matching.code !== block.code) throw new Error('The code changed. Your edits are kept.');
    content = replaceOutput(content, block.id, block.output);
  }
  return content;
}
