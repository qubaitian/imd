"""Manage document sessions through Python."""

import os
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from . import sessions
from ._service import request
from .config import load_config

TEMP_DIR = Path("/tmp")
_owner_token: str | None = None


@dataclass(frozen=True)
class Session:
    """Describe the address, start directory, and documents of a session."""

    url: str
    cwd: str
    paths: tuple[str, ...]

    @property
    def number(self) -> int:
        """Return the session number from its URL path."""
        return int(urlsplit(self.url).path.strip("/"))

    @property
    def port(self) -> int:
        """Return the public port of the shared service."""
        parts = urlsplit(self.url)
        return parts.port or (443 if parts.scheme == "https" else 80)


def create_temporary_document(cwd: Path) -> Path:
    directory = TEMP_DIR / cwd.relative_to(cwd.anchor)
    directory.mkdir(parents=True, exist_ok=True)
    name = datetime.now().astimezone().strftime("%Y-%m-%dT%H-%M-%S")
    path = directory / f"{name}-{os.getpid()}-{secrets.token_hex(4)}.md"
    path.touch(exist_ok=False)
    return path.resolve()


def _session(item: dict) -> Session:
    return Session(item["url"], item["cwd"], tuple(item["paths"]))


def open_session() -> Session:
    """Create a session with one temporary document in the current directory."""
    config = load_config()
    return _session(request("open", cwd=str(Path.cwd()), config=asdict(config)))


def list_sessions() -> list[Session]:
    """Return the live sessions on this computer."""
    return [_session(item) for item in request("list")]


def close_session(number: int) -> None:
    """Stop one session by number and keep its document files."""
    sessions.validate_number(number)
    request("close", number=number, owner_token=_owner_token)
