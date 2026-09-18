"""Send local session operations to the shared background service."""

import json
import select
import socket
import subprocess
import sys
from fcntl import LOCK_EX, LOCK_UN, flock
from time import monotonic, sleep

from . import sessions


def _socket_path() -> str:
    return str(sessions.SESSIONS_DIR / "control.sock")


def _call(payload):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(60)
        connection.connect(_socket_path())
        connection.sendall(json.dumps(payload).encode() + b"\n")
        with connection.makefile("rb") as reader:
            line = reader.readline()
    if not line:
        raise RuntimeError("The IMD service stops before it returns a result.")
    response = json.loads(line)
    if "error" in response:
        error = ValueError if response.get("kind") == "ValueError" else RuntimeError
        raise error(response["error"])
    return response["result"]


def _start(config):
    with (sessions.SESSIONS_DIR / "server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "imd._server", json.dumps(config)],
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
            start_new_session=True,
        )
    try:
        if not select.select([process.stdout], [], [], 30)[0]:
            raise RuntimeError("IMD does not start within 30 seconds.")
        if process.stdout.readline().strip() != "ready":
            detail = (sessions.SESSIONS_DIR / "server.log").read_text().strip()
            raise RuntimeError(f"IMD does not start: {detail}")
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait()
        raise
    finally:
        process.stdout.close()


def request(operation: str, **arguments):
    """Serialize session operations and start the service when open needs it."""
    sessions.SESSIONS_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (sessions.SESSIONS_DIR / "service.lock").open("a") as lock:
        flock(lock, LOCK_EX)
        try:
            try:
                _call({"operation": "ping"})
            except (FileNotFoundError, ConnectionRefusedError):
                entries = sessions.list_sessions()
                if entries:
                    raise RuntimeError(
                        "An earlier IMD service still runs. "
                        "Stop that service before using this version."
                    )
                if operation == "list":
                    return []
                if operation == "close":
                    raise ValueError("The session does not exist.")
                _start(arguments["config"])
            result = _call({"operation": operation, **arguments})
            if operation == "close" and result["last"]:
                deadline = monotonic() + 30
                while (sessions.SESSIONS_DIR / "control.sock").exists():
                    if monotonic() >= deadline:
                        raise RuntimeError(
                            "The IMD service does not stop within 30 seconds."
                        )
                    sleep(0.02)
            return result
        finally:
            flock(lock, LOCK_UN)
