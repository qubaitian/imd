export function editBlock(source, block, value) {
  if (value === (block.kind === "markdown" ? block.raw : block.code))
    return source;
  let replacement = value;
  const newline = source.includes("\r\n") ? "\r\n" : "\n";
  if (block.kind !== "markdown") {
    const old = source.slice(block.start, block.end);
    const opening = old.split(/\r?\n/, 1)[0];
    const match = opening.match(/^( {0,3})(`{3,}|~{3,})(.*)$/);
    const character = match?.[2][0] || "`";
    const runs = value.match(character === "`" ? /`+/g : /~+/g) || [];
    const fence = character.repeat(
      Math.max(3, match?.[2].length || 0, ...runs.map((run) => run.length + 1)),
    );
    const info = match?.[3] ?? block.language;
    const code = value.replace(/\r\n/g, "\n").replace(/\n/g, newline);
    replacement = `${match?.[1] || ""}${fence}${info}${newline}${code}${code && !code.endsWith(newline) ? newline : ""}${match?.[1] || ""}${fence}${newline}`;
  } else if (replacement && !replacement.endsWith("\n")) {
    replacement += newline;
  }
  return source.slice(0, block.start) + replacement + source.slice(block.end);
}

export function blockAtCursor(blocks, cursor) {
  return blocks.findIndex(
    (block) =>
      block.kind === "code" && block.start <= cursor && cursor < block.end,
  );
}

export function adjacentOutput(source, blocks, index) {
  const block = blocks[index];
  const following = blocks[index + 1];
  return block?.kind === "code" && following?.kind === "output"
    && block.parent === following.parent
    && !source.slice(block.end, following.start).trim()
    ? following
    : null;
}

export function deleteBlock(source, blocks, index) {
  const block = blocks[index];
  if (!block || !["code", "output", "text"].includes(block.kind)) return source;
  const end = adjacentOutput(source, blocks, index)?.end ?? block.end;
  return source.slice(0, block.start) + source.slice(end);
}
