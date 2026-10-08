import MarkdownIt from 'markdown-it';

const executable = new Set(['xonsh', 'shell', 'sh', 'py', 'python']);

export function renderMarkdown(content, statuses = {}, connected = true) {
  const markdown = new MarkdownIt({ html: false });
  const blocks = [];
  const escape = markdown.utils.escapeHtml;
  markdown.renderer.rules.fence = (tokens, index) => {
    const token = tokens[index];
    const language = token.info.trim().split(/\s+/)[0].toLowerCase();
    let button = '<span class="example-label">Example</span>';
    if (executable.has(language)) {
      const block = blocks.length;
      blocks.push({ language, code: token.content });
      const status = statuses[block]?.status ?? 'idle';
      const label = { queued: 'Queued', running: 'Running', ok: 'Run again', error: 'Retry', interrupted: 'Run again' }[status] ?? 'Run';
      const disabled = !connected || status === 'queued' || status === 'running';
      button = `<button class="run-button ${status}" data-block="${block}" ${disabled ? 'disabled' : ''} aria-label="${label} code block ${block + 1}"><span aria-hidden="true">${status === 'ok' ? '✓' : '▷'}</span> ${label}</button>`;
    }
    return `<section class="code-block"><div class="code-header"><span class="code-language">${escape(language || 'text')}</span>${button}</div><pre><code>${escape(token.content)}</code></pre></section>\n`;
  };
  return { html: markdown.render(content), blocks };
}
