import hashlib
import os
import re
import tempfile
from pathlib import Path

from markdown_it import MarkdownIt

PARSER = MarkdownIt("commonmark").enable("table").enable("strikethrough")


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
    for token in PARSER.parse(source):
        if token.level != 0 or token.map is None:
            continue
        start, end = (offsets[index] for index in token.map)
        if items and start < items[-1]["end"]:
            continue
        language = (
            token.info.strip().split(maxsplit=1)[0].lower()
            if token.info.strip()
            else ""
        )
        kind = "markdown"
        if token.type == "fence":
            kind = "output" if language == "out" else "code"
        items.append(
            {
                "kind": kind,
                "language": language,
                "start": start,
                "end": end,
                "start_utf16": utf16_offsets[token.map[0]],
                "end_utf16": utf16_offsets[token.map[1]],
                "raw": source[start:end],
                "code": token.content if token.type == "fence" else "",
            }
        )
    return items


def with_output(source: str, index: int, output: str) -> str:
    items = blocks(source)
    if index < 0 or index >= len(items) or items[index]["kind"] != "code":
        raise ValueError("Select a code block.")
    code = items[index]
    newline = "\r\n" if "\r\n" in source else "\n"
    output = output.replace("\r\n", "\n").replace("\r", "\n")
    longest = max((len(match[0]) for match in re.finditer(r"`+", output)), default=0)
    fence = "`" * max(3, longest + 1)
    body = output if not output or output.endswith("\n") else output + "\n"
    result = (fence + "out\n" + body + fence + "\n").replace("\n", newline)
    following = items[index + 1] if index + 1 < len(items) else None
    if (
        following
        and following["kind"] == "output"
        and not source[code["end"] : following["start"]].strip()
    ):
        return source[: following["start"]] + result + source[following["end"] :]
    before = source[: code["end"]]
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
