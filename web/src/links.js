import MarkdownIt from "markdown-it";
import DOMPurify from "dompurify";
import { Decoration, ViewPlugin } from "@codemirror/view";

const linkify = new MarkdownIt().linkify;
linkify.set({ fuzzyLink: false });

export function httpLinks(text) {
  return (linkify.match(text) || []).filter(link => /^https?:$/i.test(link.schema));
}

export function linkedHtml(html) {
  const fragment = DOMPurify.sanitize(html, { RETURN_DOM_FRAGMENT: true });
  const walker = document.createTreeWalker(fragment, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  const links = httpLinks(nodes.map(node =>
    node.parentElement?.closest("a") ? " ".repeat(node.textContent.length) : node.textContent,
  ).join(""));
  let offset = 0;
  for (const node of nodes) {
    const text = node.textContent;
    const start = offset;
    offset += text.length;
    const overlaps = links.filter(link => link.index < offset && link.lastIndex > start);
    if (!overlaps.length) continue;
    const content = document.createDocumentFragment();
    let position = 0;
    for (const link of overlaps) {
      const from = Math.max(0, link.index - start);
      const to = Math.min(text.length, link.lastIndex - start);
      content.append(text.slice(position, from));
      const span = document.createElement("span");
      span.dataset.imdUrl = link.url;
      span.className = "imd-url";
      span.title = "Cmd + click to open in Chrome";
      span.textContent = text.slice(from, to);
      content.append(span);
      position = to;
    }
    content.append(text.slice(position));
    node.replaceWith(content);
  }
  const host = document.createElement("div");
  host.append(fragment);
  return host.innerHTML;
}

export function linkedText(text) {
  const host = document.createElement("div");
  host.textContent = text;
  return linkedHtml(host.innerHTML);
}

export const editorLinks = ViewPlugin.fromClass(class {
  constructor(view) { this.updateLinks(view); }
  update(update) {
    if (update.docChanged) this.updateLinks(update.view);
  }
  updateLinks(view) {
    this.decorations = Decoration.set(httpLinks(view.state.doc.toString()).map(link =>
      Decoration.mark({
        class: "imd-url",
        attributes: { "data-imd-url": link.url, title: "Cmd + click to open in Chrome" },
      }).range(link.index, link.lastIndex),
    ));
  }
}, { decorations: value => value.decorations });

export function browserLinks(node, open) {
  const handle = event => {
    if (!event.metaKey || event.button !== 0) return;
    const link = event.target.closest?.("[data-imd-url], a[href]");
    if (!link || !node.contains(link)) return;
    const url = link.dataset.imdUrl || link.getAttribute("href");
    if (!/^https?:\/\//i.test(url)) return;
    event.preventDefault();
    event.stopPropagation();
    if (event.type === "click") open(url);
  };
  const events = ["pointerdown", "mousedown", "click"];
  for (const name of events) node.addEventListener(name, handle, true);
  return { destroy() {
    for (const name of events) node.removeEventListener(name, handle, true);
  } };
}

export function terminalLinks(terminal, lineNumber, open) {
  const buffer = terminal.buffer.active;
  let start = lineNumber - 1;
  while (start > 0 && buffer.getLine(start)?.isWrapped) start--;
  let text = "";
  const cells = [];
  for (let row = start; row < buffer.length; row++) {
    const line = buffer.getLine(row);
    if (row > start && !line.isWrapped) break;
    for (let col = 0; col < line.length; col++) {
      const cell = line.getCell(col);
      if (cell.getWidth() === 0) continue;
      const chars = cell.getChars() || " ";
      text += chars;
      for (let i = 0; i < chars.length; i++) cells.push({ x: col + 1, y: row + 1 });
    }
  }
  return httpLinks(text).map(link => ({
    text: link.url,
    range: { start: cells[link.index], end: cells[link.lastIndex - 1] },
    activate(event) {
      if (!event.metaKey) return;
      event.preventDefault();
      open(link.url);
    },
  })).filter(link => link.range.start.y <= lineNumber && link.range.end.y >= lineNumber);
}
