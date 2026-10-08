import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import httpx
import pytest
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

from imd.__main__ import main
from imd.service import close_service


@pytest.fixture
def service_environment(tmp_path):
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(("127.0.0.1", 8000))
        except OSError:
            pytest.skip("Port 8000 is already in use.")
    with tempfile.TemporaryDirectory(prefix="imd-test-", dir="/tmp") as directory:
        environment = {**os.environ, "XDG_STATE_HOME": directory}
        command_directory = tmp_path / "bin"
        command_directory.mkdir()
        command = command_directory / "imd"
        command.write_text(f"#!{sys.executable}\nfrom imd.__main__ import main\nmain()\n")
        command.chmod(0o755)
        environment["PATH"] = f"{command_directory}{os.pathsep}{environment['PATH']}"
        with patch.dict(os.environ, environment):
            try:
                yield environment
            finally:
                close_service()


def launch(environment, directory):
    result = subprocess.run(
        [sys.executable, "-m", "imd"],
        env=environment,
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def connection(directory, path="imd.md"):
    from urllib.parse import urlencode

    query = urlencode({"workspace": str(directory), "path": path})
    return connect(
        f"ws://localhost:8000/api/session?{query}", origin="http://localhost:8000", proxy=None
    )


def receive(socket, event_type):
    while True:
        event = json.loads(socket.recv(timeout=15))
        if event["type"] == event_type:
            return event


def test_bare_command_starts_in_the_background(service_environment, tmp_path):
    launch(service_environment, tmp_path)
    response = httpx.get("http://localhost:8000/", trust_env=False)
    assert response.status_code == 307
    assert response.headers["location"] == str(tmp_path)
    assert httpx.get(f"http://localhost:8000{tmp_path}", trust_env=False).status_code == 200
    assert (tmp_path / "imd.md").exists()


@pytest.mark.parametrize("arguments", [["open"], ["close"], ["--root", "."], ["--port", "8080"]])
def test_old_commands_are_removed(arguments):
    with patch.object(sys, "argv", ["imd", *arguments]), pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


def test_bare_command_restarts_and_clears_sessions(service_environment, tmp_path):
    (tmp_path / "imd.md").write_text("# Keep this document\n")
    launch(service_environment, tmp_path)
    with connection(tmp_path) as old:
        receive(old, "snapshot")
        old.send('{"type":"run","code":"value = 42"}')
        receive(old, "done")
        launch(service_environment, tmp_path)
        with pytest.raises(ConnectionClosed):
            while True:
                old.recv(timeout=5)
    with connection(tmp_path) as fresh:
        assert receive(fresh, "snapshot")["runs"] == []
        fresh.send(
            json.dumps({"type": "run", "code": "print('fresh=' + str('value' not in globals()))"})
        )
        assert receive(fresh, "done")["text"] == "fresh=True\n"
    assert (tmp_path / "imd.md").read_text() == "# Keep this document\n"


def test_restart_from_a_browser_run_survives_session_shutdown(service_environment, tmp_path):
    (tmp_path / "imd.md").write_text("")
    launch(service_environment, tmp_path)
    with connection(tmp_path) as old:
        receive(old, "snapshot")
        old.send('{"type":"run","code":"imd"}')
        with pytest.raises(ConnectionClosed):
            while True:
                old.recv(timeout=15)
    deadline = time.monotonic() + 15
    while True:
        try:
            with connection(tmp_path) as fresh:
                assert receive(fresh, "snapshot")["state"] == "ready"
                fresh.send(json.dumps({"type": "run", "code": "print('after restart')"}))
                assert receive(fresh, "done")["text"] == "after restart\n"
            break
        except (OSError, ConnectionClosed):
            assert time.monotonic() < deadline
            time.sleep(0.05)


def test_another_program_on_port_8000_is_not_stopped(service_environment, tmp_path):
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 8000))
        listener.listen()
        result = subprocess.run(
            [sys.executable, "-m", "imd"],
            env=service_environment,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        assert result.returncode == 1
        assert result.stderr
        assert listener.getsockname() == ("127.0.0.1", 8000)


def test_keyboard_interrupt_exits_without_a_traceback():
    with (
        patch.object(sys, "argv", ["imd"]),
        patch("imd.__main__.restart_service", side_effect=KeyboardInterrupt),
    ):
        main()


def test_simultaneous_commands_leave_one_ready_service(service_environment, tmp_path):
    with ThreadPoolExecutor(max_workers=2) as commands:
        results = list(commands.map(lambda _: launch(service_environment, tmp_path), range(2)))
    assert all("ready" in result.stdout for result in results)
    assert httpx.get(f"http://localhost:8000{tmp_path}", trust_env=False).status_code == 200
    with connection(tmp_path) as fresh:
        assert receive(fresh, "snapshot")["state"] == "ready"
