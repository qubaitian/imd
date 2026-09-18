import os
import socket
import sys
from pathlib import Path

import uvicorn

from . import sessions
from .app import STATIC, create_app

LISTEN_HOST = "0.0.0.0"


def session_url(port: int, token: str) -> str:
    return f"http://{LISTEN_HOST}:{port}/#token={token}"


def run_server(filename: str | list[str], cwd: Path) -> None:
    if not (STATIC / "index.html").is_file():
        print(
            "The frontend files are missing. Run npm ci and npm run build in the web directory.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    app = create_app(filename, cwd)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind((LISTEN_HOST, 0))
        bound_port = listener.getsockname()[1]
        url = session_url(bound_port, app.state.token)
        filenames = [filename] if isinstance(filename, str) else filename
        paths = [str((cwd / name).resolve()) for name in filenames]
        sessions.add_session(paths, url, os.getpid(), cwd)
        print(sessions.format_entry(url, str(cwd.resolve()), paths), flush=True)
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
        server.run(sockets=[listener])
    finally:
        listener.close()
        sessions.remove_by_pid(os.getpid())


if __name__ == "__main__":
    run_server(sys.argv[1:], Path.cwd())
