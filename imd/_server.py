import os
import socket
import sys
from pathlib import Path

import uvicorn

from . import sessions
from .app import STATIC, create_app


def run_server(filename: str | list[str], cwd: Path) -> None:
    if not (STATIC / "index.html").is_file():
        print(
            "The frontend files are missing. Run npm ci and npm run build in the web directory.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    try:
        app = create_app(filename, cwd)
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
    bound_port = listener.getsockname()[1]
    url = f"http://127.0.0.1:{bound_port}/#token={app.state.token}"
    filenames = [filename] if isinstance(filename, str) else filename
    paths = [str((cwd / name).resolve()) for name in filenames]
    try:
        sessions.add_session(paths, url, os.getpid(), cwd)
    except ValueError as error:
        listener.close()
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
    print(sessions.format_entry(url, str(cwd.resolve()), paths), flush=True)
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    try:
        server.run(sockets=[listener])
    except KeyboardInterrupt:
        pass
    finally:
        listener.close()
        sessions.remove_by_pid(os.getpid())


if __name__ == "__main__":
    run_server(sys.argv[1:], Path.cwd())
