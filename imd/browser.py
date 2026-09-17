"""Open an HTTP URL in Chrome or select an existing tab."""

import json
import subprocess
import sys
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

_lock = Lock()
_script = Path(__file__).with_name("browser.js")


def open_url(url: str) -> dict[str, str]:
    """Select a tab with the same protocol, host, and port, or open a tab."""
    try:
        parts = urlsplit(url)
        valid = (
            parts.scheme in {"http", "https"}
            and parts.hostname
            and (parts.port is None or 1 <= parts.port <= 65535)
            and not any(ord(char) < 33 for char in url)
            and "\\" not in url
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Use a complete HTTP or HTTPS URL with a valid port.")
    if sys.platform != "darwin":
        raise RuntimeError("Cmd + click requires macOS and Google Chrome.")
    with _lock:
        try:
            result = subprocess.run(
                ["osascript", "-l", "JavaScript", str(_script), url],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "Chrome does not respond. Check the macOS Automation permission and try again."
            ) from exc
        except OSError as exc:
            raise RuntimeError("macOS browser automation is not available.") from exc
    if result.returncode:
        raise RuntimeError(
            "Cannot control Google Chrome. Install Chrome and allow the app that starts IMD "
            "to control Chrome in System Settings > Privacy & Security > Automation."
        )
    try:
        data = json.loads(result.stdout)
        if data.get("action") not in {"focused", "opened"}:
            raise ValueError
    except (ValueError, AttributeError) as exc:
        raise RuntimeError("Chrome returns an invalid response.") from exc
    return {"action": data["action"]}
