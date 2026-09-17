import MarkdownIt from "markdown-it";

const markdown = new MarkdownIt("commonmark");

function codeRegion(source, pos, mode) {
  if (mode === "code") return { code: source, from: 0 };
  const lines = source.split("\n");
  const offsets = [0];
  for (const line of lines) offsets.push(offsets.at(-1) + line.length + 1);
  for (const token of markdown.parse(source, {})) {
    if (token.type !== "fence" || token.level !== 0 || token.info.trim().split(/\s+/)[0].toLowerCase() === "out") continue;
    const [startLine, endLine] = token.map;
    const from = offsets[startLine + 1];
    const closing = lines[endLine - 1]?.trim() || "";
    const closed = endLine > startLine + 1
      && closing.length >= token.markup.length
      && [...closing].every((character) => character === token.markup[0]);
    const end = closed ? offsets[endLine - 1] : source.length;
    if (from <= pos && (closed ? pos < end : pos <= end))
      return { code: source.slice(from, end), from };
  }
  return null;
}

export function kernelCompletion(request, mode) {
  return async (context) => {
    const region = codeRegion(context.state.doc.toString(), context.pos, mode);
    if (!region || context.state.readOnly) return null;
    const { code, from } = region;
    const prefix = code.slice(0, context.pos - from);
    if (!context.explicit && !/[\p{L}\p{N}_.]$/u.test(prefix)) return null;
    const controller = new AbortController();
    context.addEventListener("abort", () => controller.abort(), { onDocChange: true });
    const result = await request({ code, cursor: [...prefix].length }, controller.signal);
    if (context.aborted || controller.signal.aborted || !result?.matches?.length) return null;
    const characters = [...code];
    if (result.cursor_start < 0 || result.cursor_end < result.cursor_start || result.cursor_end > characters.length) return null;
    return {
      from: from + characters.slice(0, result.cursor_start).join("").length,
      to: from + characters.slice(0, result.cursor_end).join("").length,
      options: result.matches.map((label) => ({ label })),
    };
  };
}
