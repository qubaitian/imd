"""Restart the local service independently of its document sessions."""

import fcntl
import os
import select
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import uvicorn

from imd.server import create_app


def control_directory() -> Path:
    directory = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "imd"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


def _serve(on_ready) -> None:
    directory = control_directory()
    address = directory / "control.sock"
    with (directory / "service.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("The IMD service is already running.") from None
        server = uvicorn.Server(
            uvicorn.Config(create_app(), host="127.0.0.1", port=8000, timeout_graceful_shutdown=3)
        )
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as control:
            address.unlink(missing_ok=True)
            control.bind(str(address))
            address.chmod(0o600)
            control.listen()
            control.settimeout(0.1)
            finished = threading.Event()

            def listen():
                ready = False
                while not finished.is_set():
                    if server.started and not ready:
                        ready = True
                        on_ready()
                    try:
                        connection, _ = control.accept()
                    except TimeoutError:
                        continue
                    with connection:
                        connection.settimeout(0.5)
                        try:
                            if connection.recv(32) == b"close\n":
                                server.should_exit = True
                                connection.sendall(b"stopping\n")
                        except OSError:
                            pass

            listener = threading.Thread(target=listen, daemon=True)
            listener.start()
            try:
                server.run()
            finally:
                finished.set()
                listener.join(timeout=1)
                address.unlink(missing_ok=True)


def close_service() -> bool:
    directory = control_directory()
    deadline = time.monotonic() + 10
    requested = False
    with (directory / "service.lock").open("a") as lock:
        while time.monotonic() < deadline:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return requested
            except BlockingIOError:
                pass
            if not requested:
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as control:
                        control.settimeout(1)
                        control.connect(str(directory / "control.sock"))
                        control.sendall(b"close\n")
                        requested = control.recv(32) == b"stopping\n"
                except (FileNotFoundError, ConnectionRefusedError, TimeoutError):
                    pass
            time.sleep(0.05)
    raise RuntimeError("The IMD service did not stop within 10 seconds.")


def restart_service() -> None:
    directory = control_directory()
    reader, writer = os.pipe()
    try:
        log_fd = os.open(directory / "service.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(log_fd, "ab") as log:
            subprocess.Popen(
                [sys.executable, "-m", "imd.service", str(writer)],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
                pass_fds=(writer,),
            )
    except BaseException:
        os.close(reader)
        raise
    finally:
        os.close(writer)
    try:
        if not select.select([reader], [], [], 20)[0]:
            raise RuntimeError(
                f"The IMD service did not become ready. See {directory / 'service.log'}."
            )
        message = os.read(reader, 4096).decode().strip()
        if message != "ready":
            raise RuntimeError(
                message or f"The IMD service could not start. See {directory / 'service.log'}."
            )
    finally:
        os.close(reader)


def _restart(status: int) -> None:
    def notify(message):
        nonlocal status
        if status is None:
            return
        try:
            os.write(status, (message + "\n").encode())
        except BrokenPipeError:
            pass
        finally:
            os.close(status)
            status = None

    directory = control_directory()
    with (directory / "restart.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)

        def ready():
            notify("ready")
            fcntl.flock(lock, fcntl.LOCK_UN)

        try:
            close_service()
            _serve(ready)
        except (OSError, RuntimeError, SystemExit) as error:
            notify(f"The IMD service could not start: {error}. See {directory / 'service.log'}.")
        finally:
            notify(f"The IMD service stopped before it was ready. See {directory / 'service.log'}.")


if __name__ == "__main__":
    _restart(int(sys.argv[1]))
