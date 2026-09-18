"""Select Markdown output from literal command prefixes."""

import re
import shlex


class MarkdownCommands:
    """Validate command prefixes and match a single simple shell command."""

    def __init__(self, entries):
        if not isinstance(entries, list):
            raise ValueError("Give markdown_commands as a list of command prefixes.")
        self._prefixes = []
        for entry in entries:
            words = _words(entry) if isinstance(entry, str) else None
            if not words:
                raise ValueError(
                    "Each markdown_commands entry must be a simple command prefix."
                )
            self._prefixes.append(words)

    def matches(self, code: str, language: str) -> bool:
        if language.lower() not in {"", "shell"}:
            return False
        words = _words(code)
        return words is not None and any(
            words[: len(prefix)] == prefix for prefix in self._prefixes
        )


def _words(code):
    code = code.strip()
    quote = ""
    escaped = False
    word_start = True
    for index, char in enumerate(code):
        if escaped:
            if char == "\n":
                return None
            escaped = False
            continue
        if quote == "'":
            if char == quote:
                quote = ""
            continue
        if char == "\\":
            escaped = True
            word_start = False
            continue
        if char == "`" or code[index : index + 2] == "$(":
            return None
        if quote:
            if char == quote:
                quote = ""
            continue
        if char == "#" and word_start:
            if "\n" in code[index:]:
                return None
            code = code[:index]
            break
        if char in "\n;&|()<>{}":
            return None
        if char in "\"'":
            quote = char
        word_start = char in " \t\r"
    try:
        words = shlex.split(code)
    except ValueError:
        return None
    if not words or words[0] in {
        "if", "then", "elif", "else", "fi", "for", "while", "until", "do", "done",
        "case", "esac", "function", "select", "time", "coproc", "!", "[[", "]]",
    } or re.match(r"[A-Za-z_][A-Za-z_0-9]*=", words[0]):
        return None
    return words
