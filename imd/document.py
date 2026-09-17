import hashlib
import os
import re
import tempfile
from functools import cache
from pathlib import Path
from uuid import uuid4

from markdown_it import MarkdownIt

OUTPUT_START = re.compile(r"<!-- imd:output:begin ([A-Za-z0-9_-]+) -->")


def output_rule(state, start_line, end_line, silent):
    if state.level != 0:
        return False
    opening = state.src[state.bMarks[start_line] : state.eMarks[start_line]]
    match = OUTPUT_START.fullmatch(opening)
    if not match:
        return False

    @cache
    def find_end(first, identity):
        closing = f"<!-- imd:output:end {identity} -->"
        line = first + 1
        while line < end_line:
            text = state.src[state.bMarks[line] : state.eMarks[line]]
            if text == closing:
                return line
            nested = OUTPUT_START.fullmatch(text)
            if nested:
                nested_end = find_end(line, nested[1])
                if nested_end is not None:
                    line = nested_end + 1
                    continue
            line += 1
        return None

    last = find_end(start_line, match[1])
    if last is None:
        return False
    if not silent:
        token = state.push("imd_output", "", 0)
        token.map = [start_line, last + 1]
        token.meta["id"] = match[1]
        state.line = last + 1
    return True


PARSER = MarkdownIt("commonmark").enable("table").enable("strikethrough")
PARSER.block.ruler.before(
    "html_block", "imd_output", output_rule, {"alt": ["paragraph"]}
)


class Conflict(Exception):
    pass


def blocks(source: str) -> list[dict]:
    lines = source.splitlines(keepends=True)
    offsets = [0]
    utf16_offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
        utf16_offsets.append(utf16_offsets[-1] + len(line.encode("utf-16-le")) // 2)
    items = []

    def parse(start_line, end_line, parent=None):
        previous_end = offsets[start_line]
        for token in PARSER.parse(source[offsets[start_line] : offsets[end_line]]):
            if token.level != 0 or token.map is None:
                continue
            first, last = (start_line + line for line in token.map)
            start, end = offsets[first], offsets[last]
            if start < previous_end:
                continue
            previous_end = end
            language = (
                token.info.strip().split(maxsplit=1)[0].lower()
                if token.info.strip()
                else ""
            )
            kind = {"fence": "code", "imd_output": "output"}.get(token.type, "markdown")
            index = len(items)
            items.append(
                {
                    "kind": kind,
                    "language": language,
                    "parent": parent,
                    "start": start,
                    "end": end,
                    "start_utf16": utf16_offsets[first],
                    "end_utf16": utf16_offsets[last],
                    "raw": source[start:end],
                    "code": token.content if token.type == "fence" else "",
                }
            )
            if kind == "output":
                items[-1]["id"] = token.meta["id"]
                parse(first + 1, last - 1, index)

    parse(0, len(lines))
    return items


def with_output(source: str, index: int, output: str) -> str:
    items = blocks(source)
    if index < 0 or index >= len(items) or items[index]["kind"] != "code":
        raise ValueError("Select a code block.")
    code = items[index]
    newline = "\r\n" if "\r\n" in source else "\n"
    output = output.replace("\r\n", "\n").replace("\r", "\n")
    identity = uuid4().hex
    while identity in source or identity in output:
        identity = uuid4().hex
    body = output if not output or output.endswith("\n") else output + "\n"
    result = (
        f"<!-- imd:output:begin {identity} -->\n\n"
        + body
        + f"\n<!-- imd:output:end {identity} -->\n"
    ).replace("\n", newline)
    following = items[index + 1] if index + 1 < len(items) else None
    if (
        following
        and following["kind"] == "output"
        and following["parent"] == code["parent"]
        and not source[code["end"] : following["start"]].strip()
    ):
        return source[: following["start"]] + result + source[following["end"] :]
    before = source[: code["end"]]
    code_lines = code["raw"].splitlines()
    marker = re.match(r" {0,3}(`{3,}|~{3,})", code_lines[0])[1]
    closing = r" {0,3}" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}[ \t]*"
    if len(code_lines) == 1 or not re.fullmatch(closing, code_lines[-1]):
        before += ("" if before.endswith("\n") else newline) + marker + newline
    separation = newline if before.endswith("\n") else newline * 2
    after = source[code["end"] :]
    return (
        before
        + separation
        + result
        + (newline if after and not after.startswith(("\n", "\r")) else "")
        + after
    )


class Document:
    def __init__(self, path: Path):
        self.path = path

    @classmethod
    def open(cls, filename: str | None, cwd: Path):
        path = (cwd / (filename or "IMD.md")).resolve()
        if not path.exists():
            path.touch(exist_ok=False)
        if not path.is_file():
            raise ValueError("The document path must point to a file.")
        return cls(path)

    def read(self) -> dict:
        data = self.path.read_bytes()
        source = data.decode("utf-8")
        return {
            "name": self.path.name,
            "path": str(self.path),
            "source": source,
            "revision": hashlib.sha256(data).hexdigest(),
            "blocks": blocks(source),
        }

    def save(self, source: str, revision: str) -> dict:
        current = self.read()
        if current["revision"] != revision:
            raise Conflict(
                "The file changed in another program. Keep the current content. Then reload the file."
            )
        if source == current["source"]:
            return current
        data = source.encode("utf-8")
        descriptor, name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", dir=self.path.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                os.fchmod(stream.fileno(), self.path.stat().st_mode & 0o777)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if self.read()["revision"] != revision:
                raise Conflict(
                    "The file changed during save. Keep the current content."
                )
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return self.read()
