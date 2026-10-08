"""Read and replace the output linked to an executable Markdown block."""

import re

from markdown_it import MarkdownIt

LANGUAGES = {"xonsh", "shell", "sh", "py", "python"}
MARKER = re.compile(r"<!--\s*([a-f0-9]{6,32})\s*-->")


def output_block(content: str, marker: str) -> dict:
    tokens = MarkdownIt("commonmark").parse(content)
    matches = [
        index
        for index, token in enumerate(tokens)
        if token.type == "html_block"
        and (match := MARKER.fullmatch(token.content.strip()))
        and match[1] == marker
    ]
    if len(matches) != 1:
        raise ValueError("The output marker is missing or duplicated.")
    index = matches[0]
    if index < 1 or index + 1 >= len(tokens):
        raise ValueError("The output marker must be between code and output.")
    code, output = tokens[index - 1], tokens[index + 1]
    if (
        code.type != "fence"
        or (code.info.strip().split() or [""])[0].lower() not in LANGUAGES
        or output.type != "fence"
        or output.info.strip() != "txt"
    ):
        raise ValueError("The output marker must follow executable code and precede a txt fence.")
    return {"id": marker, "code": code.content, "output": output.content, "map": output.map}


def replace_output(content: str, marker: str, text: str, expected_code: str | None = None) -> str:
    block = output_block(content, marker)
    if expected_code is not None and block["code"] != expected_code:
        raise ValueError("The code changed during the run. The result was not saved.")
    lines = content.splitlines(keepends=True)
    start, end = block["map"]
    opener = re.match(r"^(.*?)(?:`{3,}|~{3,})", lines[start])
    prefix = opener[1]
    fence = "`" * max(3, 1 + max((len(m[0]) for m in re.finditer(r"`+", text)), default=0))
    body = "".join(prefix + line + "\n" for line in text.splitlines())
    replacement = f"{prefix}{fence}txt\n{body}{prefix}{fence}\n"
    return "".join(lines[:start]) + replacement + "".join(lines[end:])
