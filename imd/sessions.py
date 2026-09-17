import ast
import json
import os
from contextlib import contextmanager
from fcntl import LOCK_EX, LOCK_UN, flock
from pathlib import Path
from urllib.parse import urlsplit

SESSIONS_DIR = Path(os.environ.get("IMD_SESSIONS_DIR", Path.home() / ".imd"))
SESSIONS_FILE = SESSIONS_DIR / "sessions.json"


def format_entry(url: str, cwd: str, paths: list[str] | tuple[str, ...]) -> str:
    values = (url, cwd, *paths)
    return (
        "(" + ", ".join(json.dumps(value, ensure_ascii=False) for value in values) + ")"
    )


def parse_entry(line: str) -> tuple[str, ...]:
    try:
        values = ast.literal_eval(line)
        if (
            isinstance(values, tuple)
            and len(values) >= 2
            and all(isinstance(item, str) for item in values)
            and urlsplit(values[0]).scheme == "http"
            and urlsplit(values[0]).port is not None
        ):
            return values
    except (ValueError, SyntaxError, TypeError):
        pass
    raise ValueError(f"Invalid session entry: {line}")


def validate_port(port: int) -> int:
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Give a port from 1 through 65535.")
    return port


def is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    else:
        return True


@contextmanager
def _locked_registry():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    with SESSIONS_FILE.open("a+", encoding="utf-8") as handle:
        flock(handle.fileno(), LOCK_EX)
        handle.seek(0)
        yield handle
        flock(handle.fileno(), LOCK_UN)


def _read_sessions(handle) -> list[dict]:
    raw = handle.read()
    if not raw.strip():
        return []
    return json.loads(raw)


def _write_sessions(handle, sessions: list[dict]) -> None:
    handle.seek(0)
    handle.truncate()
    json.dump(sessions, handle, indent=2)
    handle.write("\n")
    handle.flush()


def _prune(sessions: list[dict]) -> list[dict]:
    return [item for item in sessions if is_alive(item["pid"])]


def _load(handle) -> list[dict]:
    sessions = _prune(_read_sessions(handle))
    _write_sessions(handle, sessions)
    return sessions


def _save(handle, sessions: list[dict]) -> None:
    _write_sessions(handle, _prune(sessions))


def add_session(paths: list[str], url: str, pid: int, cwd: Path) -> None:
    entry = {
        "paths": [str(Path(path).resolve()) for path in paths],
        "url": url,
        "cwd": str(cwd.resolve()),
        "pid": pid,
    }
    with _locked_registry() as handle:
        sessions = _load(handle)
        sessions.append(entry)
        _save(handle, sessions)


def remove_by_pid(pid: int) -> None:
    with _locked_registry() as handle:
        sessions = _load(handle)
        sessions = [item for item in sessions if item["pid"] != pid]
        _save(handle, sessions)


def list_sessions() -> list[dict]:
    with _locked_registry() as handle:
        return _load(handle)


def remove_session(port: int, *, protected_pid: int | None = None) -> dict | None:
    validate_port(port)
    with _locked_registry() as handle:
        sessions = _load(handle)
        for index, item in enumerate(sessions):
            if urlsplit(item["url"]).port == port:
                if item["pid"] == protected_pid:
                    raise ValueError("A kernel cannot close its own session.")
                removed = sessions.pop(index)
                _save(handle, sessions)
                return removed
        return None
