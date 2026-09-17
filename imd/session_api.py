"""Manage document sessions through Python."""

import os
import secrets
import select
import signal
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from . import sessions

TEMP_DIR = Path("/tmp")
_owner_pid: int | None = None


@dataclass(frozen=True)
class Session:
    """Describe the address, start directory, and documents of a session."""

    url: str
    cwd: str
    paths: tuple[str, ...]

    @property
    def port(self) -> int:
        """Return the session port."""
        return urlsplit(self.url).port


def create_temporary_document(cwd: Path) -> Path:
    directory = TEMP_DIR / cwd.relative_to(cwd.anchor)
    directory.mkdir(parents=True, exist_ok=True)
    name = datetime.now().astimezone().strftime("%Y-%m-%dT%H-%M-%S")
    path = directory / f"{name}-{os.getpid()}-{secrets.token_hex(4)}.md"
    path.touch(exist_ok=False)
    return path


def open_session() -> Session:
    """Create a session with one temporary document in the current directory."""
    cwd = Path.cwd()
    path = create_temporary_document(cwd)
    process = subprocess.Popen(
        [sys.executable, "-m", "imd._server", str(path)],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )
    started = False
    try:
        if not select.select([process.stdout], [], [], 30)[0]:
            raise RuntimeError("imd does not start within 30 seconds.")
        line = process.stdout.readline().strip()
        if process.poll() is not None or not line:
            raise RuntimeError("imd does not start.")
        url, saved_cwd, *paths = sessions.parse_entry(line)
        started = True
        return Session(url, saved_cwd, tuple(paths))
    finally:
        process.stdout.close()
        if not started:
            if process.poll() is None:
                process.kill()
            process.wait()


def list_sessions() -> list[Session]:
    """Return the live sessions on this computer."""
    result = []
    for item in sessions.list_sessions():
        if "cwd" not in item:
            port = urlsplit(item["url"]).port
            raise ValueError(
                f"Session {port} has no saved start directory. "
                f"Run imd close {port}, then imd open."
            )
        result.append(Session(item["url"], item["cwd"], tuple(item["paths"])))
    return result


def close_session(port: int) -> None:
    """Stop a session by port and keep its document files."""
    sessions.validate_port(port)
    item = sessions.remove_session(port, protected_pid=_owner_pid)
    if item is None:
        raise ValueError("The session does not exist.")
    os.kill(item["pid"], signal.SIGTERM)
