"""Resolve local paths and open directory sessions."""

import subprocess
import sys
from pathlib import Path
from threading import Lock

from . import browser, sessions

_directory_lock = Lock()


def resolve_path(value: str, cwd: Path) -> Path:
    """Resolve a path from the fixed session start directory."""
    if not value or "\x00" in value or "\n" in value or "\r" in value:
        raise ValueError("Give a local file or directory path.")
    path = (cwd / value).resolve(strict=True)
    if not path.is_dir():
        read_text(path)
    return path


def read_text(path: Path) -> str:
    """Read a regular UTF-8 text file and reject binary content."""
    if not path.is_file():
        raise ValueError("The path must refer to a file or directory.")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise ValueError("The file is not a UTF-8 text file.") from exc
    if any(ord(char) < 32 and char not in "\t\n\r\f" for char in text):
        raise ValueError("Binary files cannot open in a document panel.")
    return text


def open_directory(path: Path) -> dict:
    """Open the latest matching session or run open in the directory."""
    with _directory_lock:
        matches = [
            entry
            for entry in sessions.list_sessions()
            if entry.get("cwd") and Path(entry["cwd"]).resolve() == path
        ]
        if matches:
            url = matches[-1]["url"]
        else:
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "imd.cli", "open"],
                    cwd=path,
                    capture_output=True,
                    text=True,
                    timeout=40,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise RuntimeError("The directory session does not start.") from exc
            if result.returncode:
                raise RuntimeError(
                    result.stderr.strip() or "The directory session does not start."
                )
            url, *_ = sessions.parse_entry(result.stdout.strip())
    return browser.open_url(url, match_path=True)
