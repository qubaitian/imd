"""Read service settings from the current user's configuration file."""

import runpy
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from .output_format import MarkdownCommands


@dataclass(frozen=True)
class Config:
    host: str = "0.0.0.0"
    port: int = 8000
    public_url: str = "http://0.0.0.0:8000"
    markdown_commands: list[str] = field(default_factory=list)


def load_config() -> Config:
    """Execute ~/.imd/config.py and validate its config dictionary."""
    path = Path.home() / ".imd" / "config.py"
    if not path.exists():
        return Config()
    try:
        config = runpy.run_path(str(path))["config"]
        if not isinstance(config, dict):
            raise TypeError("Define config as a dictionary.")
        unknown = config.keys() - {"host", "port", "public_url", "markdown_commands"}
        if unknown:
            raise ValueError(f"Unknown settings: {', '.join(sorted(unknown))}.")
        host = config.get("host", "0.0.0.0")
        port = config.get("port", 8000)
        if (
            not isinstance(host, str)
            or not host
            or any(char.isspace() for char in host)
        ):
            raise ValueError("Give a listen host.")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Give a port from 1 through 65535.")
        url_host = f"[{host}]" if ":" in host else host
        public_url = config.get("public_url", f"http://{url_host}:{port}")
        if not isinstance(public_url, str):
            raise TypeError("Give a public URL.")
        parts = urlsplit(public_url)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.path not in {"", "/"}
            or parts.query
            or parts.fragment
            or any(char.isspace() for char in public_url)
            or (parts.port is not None and not 1 <= parts.port <= 65535)
        ):
            raise ValueError(
                "Use an HTTP or HTTPS public URL without a path, query, or token."
            )
        markdown_commands = config.get("markdown_commands", [])
        MarkdownCommands(markdown_commands)
        return Config(host, port, public_url.rstrip("/"), markdown_commands)
    except Exception as exc:
        raise ValueError(f"Invalid configuration in {path}: {exc}") from exc
