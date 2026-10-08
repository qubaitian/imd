import { analyzeDocument } from './document.js';

export function renderMarkdown(content, statuses = {}, connected = true) {
  const { markdown, tokens, blocks, markers, outputs } = analyzeDocument(content);
  const escape = markdown.utils.escapeHtml;
  const editableBlocks = [];
  markdown.renderer.rules.fence = (tokens, index) => {
    const token = tokens[index];
    const language = token.info.trim().split(/\s+/)[0].toLowerCase();
    let button = '<span class="example-label">Example</span>';
    let editable = true;
    if (outputs.has(token)) {
      const output = outputs.get(token);
      return `<section class="output-block"><div data-output-slot="${output.id}"></div></section>\n`;
    }
    const block = blocks.findIndex((candidate) => candidate.token === token);
    if (block !== -1) {
      const status = statuses[block]?.status ?? 'idle';
      editable = status !== 'queued' && status !== 'running';
      const label = { queued: 'Queued', running: 'Running', ok: 'Run again', error: 'Retry', interrupted: 'Run again' }[status] ?? 'Run';
      const disabled = !connected || status === 'queued' || status === 'running';
      button = `<button class="run-button ${status}" data-block="${block}" ${disabled ? 'disabled' : ''} aria-label="${label} code block ${block + 1}"><span aria-hidden="true">${status === 'ok' ? '✓' : '▷'}</span> ${label}</button>`;
    }
    const slot = editableBlocks.length;
    editableBlocks.push({ code: token.content, info: token.info, map: token.map, editable });
    return `<section class="code-block"><div class="code-header"><span class="code-language">${escape(language || 'text')}</span>${button}</div><div data-code-slot="${slot}"><pre><code>${escape(token.content)}</code></pre></div></section>\n`;
  };
  markdown.renderer.rules.html_block = (tokens, index) => markers.has(tokens[index]) ? '' : escape(tokens[index].content);
  markdown.renderer.rules.html_inline = (tokens, index) => escape(tokens[index].content);
  return { html: markdown.renderer.render(tokens, markdown.options, {}), blocks, editableBlocks,
    outputs: [...outputs.values()].map((block) => ({ id: block.id, text: block.output })) };
}
