import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import FastAPI

import imd
from imd import sessions
from imd._server import Service
from imd.config import Config


@pytest.fixture
def server(tmp_path, monkeypatch):
    with TemporaryDirectory(prefix="imd-test-", dir="/tmp") as home:
        directory = Path(home) / ".imd"
        directory.mkdir()
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        config_path = directory / "config.py"
        config_path.write_text(
            f'config = {{"host": "127.0.0.1", "port": {port}, '
            '"public_url": "https://qubaitian.duckdns.org"}\n'
        )
        monkeypatch.setenv("HOME", home)
        monkeypatch.setenv("IMD_SESSIONS_DIR", str(directory))
        monkeypatch.setattr(sessions, "SESSIONS_DIR", directory)
        monkeypatch.setattr(sessions, "SESSIONS_FILE", directory / "sessions.json")
        monkeypatch.chdir(tmp_path)
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", trust_env=False
        ) as client:
            yield client, config_path
        for entry in imd.list():
            imd.close(entry.number)


def headers(entry):
    token = parse_qs(urlsplit(entry.url).fragment)["token"][0]
    return {"Authorization": f"Bearer {token}"}


def test_sessions_share_port_and_keep_separate_paths_tokens_and_files(server, tmp_path):
    client, _ = server
    first = imd.open()
    second = imd.open()
    assert first.number != second.number
    assert first.port == second.port == 443
    assert first.url.startswith(f"https://qubaitian.duckdns.org/{first.number}/#token=")
    assert first.cwd == second.cwd == str(tmp_path)
    assert first.paths != second.paths
    assert imd.list() == [first, second]
    for entry in (first, second):
        response = client.get(f"/{entry.number}/api/document", headers=headers(entry))
        assert response.status_code == 200
        assert response.json()["path"] == entry.paths[0]
        assert client.get(f"/{entry.number}/").status_code == 200
    assert (
        client.get(f"/{second.number}/api/document", headers=headers(first)).status_code
        == 401
    )
    assert client.get("/api/session").status_code == 404
    imd.close(first.number)
    assert Path(first.paths[0]).is_file()
    assert imd.list() == [second]
    assert client.get(f"/{first.number}/").status_code == 404
    assert (
        client.get(f"/{second.number}/api/session", headers=headers(second)).status_code
        == 200
    )
    imd.close(second.number)
    assert imd.list() == []
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", client.base_url.port))
    third = imd.open()
    assert third.number > second.number


def test_cli_and_api_use_the_same_session_information(server):
    entry = imd.open()
    result = subprocess.run(
        [sys.executable, "-m", "imd.cli", "list"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert sessions.parse_entry(result.stdout.strip()) == (
        entry.url,
        entry.cwd,
        *entry.paths,
    )
    result = subprocess.run(
        [sys.executable, "-m", "imd.cli", "open"],
        capture_output=True,
        text=True,
        check=True,
    )
    opened = sessions.parse_entry(result.stdout.strip())
    second = imd.list()[-1]
    assert opened == (second.url, second.cwd, *second.paths)
    subprocess.run(
        [sys.executable, "-m", "imd.cli", "close", str(entry.number)], check=True
    )
    assert imd.list() == [second]


def test_concurrent_open_starts_one_service(server):
    with ThreadPoolExecutor(max_workers=3) as pool:
        entries = list(pool.map(lambda _: imd.open(), range(3)))
    assert len({entry.number for entry in entries}) == 3
    records = json.loads(sessions.SESSIONS_FILE.read_text())
    assert len({entry["pid"] for entry in records}) == 1
    assert {entry.number for entry in imd.list()} == {entry.number for entry in entries}


def test_config_change_requires_closing_existing_sessions(server):
    _, config_path = server
    entry = imd.open()
    config_path.write_text(
        config_path.read_text().replace("qubaitian.duckdns.org", "example.com")
    )
    with pytest.raises(ValueError, match="Close all sessions"):
        imd.open()
    assert imd.list() == [entry]
    imd.close(entry.number)
    assert imd.open().url.startswith("https://example.com/")


def test_busy_port_does_not_fall_back_to_a_random_port(server):
    client, _ = server
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", client.base_url.port))
        listener.listen()
        with pytest.raises(RuntimeError, match="port|Address already in use"):
            imd.open()
    assert imd.list() == []


def test_session_number_validation(server):
    for number in (0, -1, True, "1"):
        with pytest.raises(ValueError, match="session number"):
            imd.close(number)


def test_kernel_can_manage_other_sessions_but_cannot_close_its_own_session(server):
    client, _ = server
    entry = imd.open()
    source = (
        "```python\n"
        "new_session = imd.open()\n"
        "imd.close(new_session.number)\n"
        f"imd.close({entry.number})\n"
        "```\n"
    )
    document = client.get(
        f"/{entry.number}/api/document", headers=headers(entry)
    ).json()
    response = client.post(
        f"/{entry.number}/api/execute",
        headers=headers(entry),
        json={"source": source, "revision": document["revision"], "block": 0},
        timeout=45,
    )
    assert response.status_code == 200
    assert "A kernel cannot close its own session" in response.json()["source"]
    assert imd.list() == [entry]


def test_nested_document_assets_use_session_path(server, tmp_path):
    client, _ = server
    entry = imd.open()
    path = tmp_path / "second.md"
    path.write_text("# Second\n")
    (tmp_path / "image.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    response = client.post(
        f"/{entry.number}/api/paths/open",
        headers=headers(entry),
        json={"path": str(path)},
    )
    assert response.status_code == 200
    base = response.json()["document"]["base"]
    document_url = f"/{entry.number}{base}/api/document"
    assert client.get(document_url, headers=headers(entry)).status_code == 200
    assert client.get(f"/{entry.number}{base}/api/assets/image.svg").status_code == 200
    assert imd.list()[0].paths == (*entry.paths, str(path))


def test_stopped_service_does_not_block_a_new_open(server):
    entry = imd.open()
    pid = json.loads(sessions.SESSIONS_FILE.read_text())[0]["pid"]
    os.kill(pid, signal.SIGKILL)
    deadline = monotonic() + 5
    while True:
        with socket.socket(socket.AF_UNIX) as connection:
            if connection.connect_ex(str(sessions.SESSIONS_DIR / "control.sock")):
                break
        assert monotonic() < deadline
        sleep(0.01)
    try:
        assert imd.list() == []
        assert imd.open().number > entry.number
    finally:
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass


def test_invalid_config_does_not_prevent_list_or_close(server):
    _, config_path = server
    entry = imd.open()
    config_path.write_text("config = None\n")
    with pytest.raises(ValueError, match="config.py"):
        imd.open()
    assert imd.list() == [entry]
    imd.close(entry.number)
    assert imd.list() == []


def test_each_open_uses_the_callers_directory(server, tmp_path, monkeypatch):
    client, _ = server
    first = imd.open()
    directory = tmp_path / "second"
    directory.mkdir()
    monkeypatch.chdir(directory)
    second = imd.open()
    assert first.cwd == str(tmp_path)
    assert second.cwd == str(directory)
    for entry in (first, second):
        data = client.get(f"/{entry.number}/api/session", headers=headers(entry)).json()
        assert data["cwd"] == entry.cwd


def close_all(interface):
    if interface == "api":
        assert imd.close() is None
    else:
        result = subprocess.run(
            [sys.executable, "-m", "imd.cli", "close"],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout == result.stderr == ""


def assert_service_stops(client):
    assert not (sessions.SESSIONS_DIR / "control.sock").exists()
    assert imd.list() == []
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", client.base_url.port))


@pytest.mark.parametrize("interface", ["api", "cli"])
def test_close_all_keeps_files_and_stops_service(
    server, tmp_path, monkeypatch, interface
):
    client, config_path = server
    first = imd.open()
    directory = tmp_path / "second"
    directory.mkdir()
    monkeypatch.chdir(directory)
    second = imd.open()
    paths = [Path(entry.paths[0]) for entry in (first, second)]
    for path in paths:
        path.write_text("# Keep this file\n")
    config_path.write_text("config = None\n")

    close_all(interface)

    assert_service_stops(client)
    assert all(path.read_text() == "# Keep this file\n" for path in paths)


@pytest.mark.parametrize("interface", ["api", "cli"])
def test_close_all_without_sessions_succeeds_without_starting_service(
    server, interface
):
    client, config_path = server
    config_path.write_text("config = None\n")
    close_all(interface)
    close_all(interface)
    assert_service_stops(client)
    assert not (sessions.SESSIONS_DIR / "server.log").exists()


@pytest.mark.parametrize("interface", ["api", "cli"])
def test_close_all_from_kernel_stops_other_sessions_and_itself(
    server, tmp_path, interface
):
    client, _ = server
    caller = imd.open()
    other = imd.open()
    command = (
        "imd.close()" if interface == "api" else f"!{sys.executable} -m imd.cli close"
    )
    document = client.get(
        f"/{caller.number}/api/document", headers=headers(caller)
    ).json()
    marker = tmp_path / "sessions-at-caller-close.json"
    source = (
        "```python\n"
        "from pathlib import Path\n"
        "try:\n"
        f"    {command}\n"
        "finally:\n"
        f"    Path({str(marker)!r}).write_text(\n"
        f"        Path({str(sessions.SESSIONS_FILE)!r}).read_text())\n"
        "```\n"
    )
    response = client.post(
        f"/{caller.number}/api/execute",
        headers=headers(caller),
        json={"source": source, "revision": document["revision"], "block": 0},
        timeout=45,
    )
    assert response.status_code == 200
    deadline = monotonic() + 10
    while (sessions.SESSIONS_DIR / "control.sock").exists():
        assert monotonic() < deadline, response.text
        sleep(0.02)
    assert_service_stops(client)
    assert all(Path(entry.paths[0]).is_file() for entry in (caller, other))
    assert [entry["number"] for entry in json.loads(marker.read_text())] == [
        caller.number
    ]


def test_close_all_interrupts_running_code(server, tmp_path):
    client, _ = server
    entry = imd.open()
    imd.open()
    marker = tmp_path / "running"
    source = (
        "```python\n"
        "from pathlib import Path\n"
        "import time\n"
        f"Path({str(marker)!r}).touch()\n"
        "time.sleep(60)\n"
        "```\n"
    )
    document = client.get(
        f"/{entry.number}/api/document", headers=headers(entry)
    ).json()
    with ThreadPoolExecutor(max_workers=1) as pool:
        execution = pool.submit(
            client.post,
            f"/{entry.number}/api/execute",
            headers=headers(entry),
            json={"source": source, "revision": document["revision"], "block": 0},
            timeout=45,
        )
        try:
            deadline = monotonic() + 20
            while not marker.exists():
                assert monotonic() < deadline
                sleep(0.02)
            imd.close()
            assert_service_stops(client)
            assert "KeyboardInterrupt" in execution.result(timeout=10).json()["source"]
        finally:
            for remaining in imd.list():
                imd.close(remaining.number)


@pytest.mark.parametrize("failures", [False, True])
def test_close_all_closes_caller_last_and_continues_after_errors(
    server, tmp_path, monkeypatch, failures
):
    closed = []
    tokens = []

    def create_app(filename, cwd, token):
        tokens.append(token)

        @asynccontextmanager
        async def lifespan(app):
            yield
            closed.append(token)
            if failures and token in tokens[:2]:
                raise RuntimeError(f"Cannot close session {tokens.index(token) + 1}.")

        app = FastAPI(lifespan=lifespan)
        app.state.token = token
        return app

    monkeypatch.setattr("imd._server.create_app", create_app)

    async def run():
        service = Service(Config())
        for _ in range(3):
            await service.open(tmp_path)
        request = {"operation": "close", "number": None, "owner_token": tokens[0]}
        if failures:
            with pytest.raises(RuntimeError) as error:
                await service.dispatch(request)
            assert "Cannot close session 1" in str(error.value)
            assert "Cannot close session 2" in str(error.value)
        else:
            assert await service.dispatch(request) == {"last": True}
        assert closed == [tokens[1], tokens[2], tokens[0]]
        assert service.server.should_exit
        assert sessions.list_sessions() == []

    try:
        asyncio.run(run())
    finally:
        sessions.remove_by_pid(os.getpid())
