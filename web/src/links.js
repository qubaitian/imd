import MarkdownIt from "markdown-it";
import DOMPurify from "dompurify";
import { Decoration, ViewPlugin } from "@codemirror/view";

const linkify = new MarkdownIt().linkify;
linkify.set({ fuzzyLink: false });

export function httpLinks(text) {
  return (linkify.match(text) || []).filter(link => /^https?:$/i.test(link.schema));
}

function isLocalPath(text) {
  if (!text || /^(?:[a-z][\w+.-]*:|www\.|#|\/\/)/i.test(text)) return false;
  return /^(?:\/|\.\.?\/)/.test(text)
    || /^[^\s/]+\/.+/.test(text)
    || /^[^\s/]+\.[a-z][a-z0-9_-]*$/i.test(text);
}

function linksIn(text) {
  const links = httpLinks(text).map(link => ({ ...link, kind: "url" }));
  const tokens = /(["'`])([^"'`\r\n]+)\1|[^\s<>"'`()\[\]{},;=|\\]+/g;
  for (const match of text.matchAll(tokens)) {
    const quoted = Boolean(match[1]);
    const value = quoted ? match[2] : match[0].replace(/[.!?:。，！：；]+$/, "");
    const index = match.index + (quoted ? 1 : 0);
    const lastIndex = index + value.length;
    if (text[index - 1] === "<" && /^\/?[a-z][\w:-]*$/i.test(value)) continue;
    if (!isLocalPath(value) || links.some(link => link.index < lastIndex && link.lastIndex > index)) continue;
    links.push({ index, lastIndex, url: value, kind: "path" });
  }
  return links.sort((a, b) => a.index - b.index);
}

function attributes(link) {
  return {
    [`data-imd-${link.kind}`]: link.url,
    title: link.kind === "url" ? "Cmd + click to open in Chrome" : "Cmd + click to open this path",
  };
}

export function linkedHtml(html) {
  const fragment = DOMPurify.sanitize(html, { RETURN_DOM_FRAGMENT: true });
  const walker = document.createTreeWalker(fragment, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  const links = linksIn(nodes.map(node =>
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
      for (const [name, value] of Object.entries(attributes(link))) span.setAttribute(name, value);
      span.className = `imd-${link.kind}`;
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
    this.decorations = Decoration.set(linksIn(view.state.doc.toString()).map(link =>
      Decoration.mark({
        class: `imd-${link.kind}`,
        attributes: attributes(link),
      }).range(link.index, link.lastIndex),
    ));
  }
}, { decorations: value => value.decorations });

export function followLinks(node, open) {
  const handle = event => {
    if (!event.metaKey || event.button !== 0) return;
    const link = event.target.closest?.("[data-imd-url], [data-imd-path], a[href]");
    if (!link || !node.contains(link)) return;
    let url = link.dataset.imdUrl || link.dataset.imdPath || link.getAttribute("href");
    if (!/^https?:\/\//i.test(url)) {
      if (!link.dataset.imdPath) {
        try { url = decodeURIComponent(url); } catch { return; }
      }
      if (!isLocalPath(url)) return;
    }
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
  return linksIn(text).map(link => ({
    text: link.url,
    range: { start: cells[link.index], end: cells[link.lastIndex - 1] },
    activate(event) {
      if (!event.metaKey) return;
      event.preventDefault();
      open(link.url);
    },
  })).filter(link => link.range.start.y <= lineNumber && link.range.end.y >= lineNumber);
}
