import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from imd import browser, sessions
from imd.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    registry = tmp_path / "registry"
    monkeypatch.setattr(sessions, "SESSIONS_DIR", registry)
    monkeypatch.setattr(sessions, "SESSIONS_FILE", registry / "sessions.json")
    (tmp_path / "start.md").write_text("# Start\n")
    with TestClient(create_app("start.md", tmp_path, token="paths-test")) as client:
        client.headers["Authorization"] = "Bearer paths-test"
        yield client


def test_file_paths_add_documents_and_keep_the_start_directory(client, tmp_path):
    folder = tmp_path / "nested"
    folder.mkdir()
    path = folder / "next.md"
    path.write_text("# Next\n")
    (tmp_path / "root.md").write_text("# Root\n")
    result = client.post("/api/paths/open", json={"path": "nested/next.md"})
    assert result.status_code == 200
    item = result.json()["document"]
    assert item["path"] == str(path.resolve())
    assert item["readonly"] is False
    opened = client.get(f"{item['base']}/api/document").json()
    saved = client.put(
        f"{item['base']}/api/document",
        json={"source": "# Changed\n", "revision": opened["revision"]},
    )
    assert saved.status_code == 200
    assert path.read_text() == "# Changed\n"
    assert client.post("/api/paths/open", json={"path": "root.md"}).status_code == 200
    assert client.post("/api/paths/open", json={"path": str(path)}).status_code == 200
    documents = client.get("/api/session").json()["documents"]
    assert len(documents) == 4
    assert documents[1] == documents[3]


def test_text_is_readonly_and_invalid_paths_do_not_create_files(client, tmp_path):
    (tmp_path / "script.py").write_text("print('hello')\n")
    result = client.post("/api/paths/open", json={"path": "./script.py"})
    assert result.status_code == 200
    item = result.json()["document"]
    assert item["readonly"] is True
    data = client.get(f"{item['base']}/api/document").json()
    assert data["source"] == "print('hello')\n"
    for operation in ["document", "execute", "complete"]:
        method = "PUT" if operation == "document" else "POST"
        response = client.request(
            method,
            f"{item['base']}/api/{operation}",
            json={
                "source": data["source"],
                "revision": data["revision"],
                "block": 0,
                "code": "",
                "cursor": 0,
            },
        )
        assert response.status_code == 403
    (tmp_path / "binary.dat").write_bytes(b"hello\x00world")
    (tmp_path / "invalid.dat").write_bytes(b"\xff\xfe")
    for path in ["binary.dat", "invalid.dat", "missing.md"]:
        response = client.post("/api/paths/open", json={"path": path})
        assert response.status_code in {400, 404}
    assert not (tmp_path / "missing.md").exists()
    assert len(client.get("/api/session").json()["documents"]) == 2


def test_path_endpoint_requires_the_session_token(client, tmp_path, monkeypatch):
    monkeypatch.setattr(browser, "open_url", lambda url: pytest.fail("Chrome opens."))
    client.headers.clear()
    assert (
        client.post("/api/paths/open", json={"path": str(tmp_path)}).status_code == 401
    )


def test_directory_selects_latest_matching_session(client, tmp_path, monkeypatch):
    folder = tmp_path / "target"
    folder.mkdir()
    calls = []
    records = [
        {"cwd": str(folder.resolve()), "url": "http://127.0.0.1:8001/#token=old"},
        {"cwd": str(folder.resolve()), "url": "http://127.0.0.1:8002/#token=new"},
        {"cwd": str(tmp_path.resolve()), "url": "http://127.0.0.1:8003/#token=other"},
    ]
    monkeypatch.setattr(sessions, "list_sessions", lambda: records)
    monkeypatch.setattr(
        browser, "open_url", lambda url: calls.append(url) or {"action": "focused"}
    )
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: pytest.fail("A session starts.")
    )
    response = client.post("/api/paths/open", json={"path": "./target"})
    assert response.status_code == 200
    assert response.json()["action"] == "focused"
    assert calls == [records[1]["url"]]
    assert len(client.get("/api/session").json()["documents"]) == 1


def test_directory_runs_open_in_target_directory(client, tmp_path, monkeypatch):
    folder = tmp_path / "space directory"
    folder.mkdir()
    url = "http://127.0.0.1:8123/#token=new"
    calls = []
    monkeypatch.setattr(sessions, "list_sessions", list)

    def run(args, **kwargs):
        assert args == [sys.executable, "-m", "imd.cli", "open"]
        assert Path(kwargs["cwd"]) == folder.resolve()
        assert not kwargs.get("shell")
        return subprocess.CompletedProcess(
            args, 0, sessions.format_entry(url, str(folder), ["/tmp/new.md"]), ""
        )

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(
        browser, "open_url", lambda value: calls.append(value) or {"action": "opened"}
    )
    response = client.post("/api/paths/open", json={"path": "./space directory"})
    assert response.status_code == 200
    assert calls == [url]
    assert len(client.get("/api/session").json()["documents"]) == 1


def test_repeated_file_panels_report_save_conflicts(client, tmp_path):
    path = tmp_path / "next.md"
    path.write_text("# Original\n")
    first = client.post("/api/paths/open", json={"path": str(path)}).json()["document"]
    second = client.post("/api/paths/open", json={"path": str(path)}).json()["document"]
    data = client.get(f"{first['base']}/api/document").json()
    assert (
        client.put(
            f"{first['base']}/api/document",
            json={
                "source": "# First\n",
                "revision": data["revision"],
            },
        ).status_code
        == 200
    )
    response = client.put(
        f"{second['base']}/api/document",
        json={
            "source": "# Second\n",
            "revision": data["revision"],
        },
    )
    assert response.status_code == 409
    assert "changed" in response.json()["detail"]
    assert path.read_text() == "# First\n"


def test_open_files_update_python_and_cli_session_information(
    client, tmp_path, monkeypatch
):
    from imd.session_api import list_sessions

    sessions.add_session(
        [str(tmp_path / "start.md")],
        "http://127.0.0.1:8123/#token=paths-test",
        os.getpid(),
        tmp_path,
    )
    path = tmp_path / "next.md"
    path.write_text("# Next\n")
    for _ in range(2):
        assert (
            client.post("/api/paths/open", json={"path": str(path)}).status_code == 200
        )
    expected = (str(tmp_path / "start.md"), str(path), str(path))
    entry = list_sessions()[0]
    assert entry.paths == expected
    monkeypatch.setenv("IMD_SESSIONS_DIR", str(sessions.SESSIONS_DIR))
    result = subprocess.run(
        [sys.executable, "-m", "imd.cli", "list"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert sessions.parse_entry(result.stdout.strip()) == (
        entry.url,
        entry.cwd,
        *expected,
    )


def test_new_document_kernel_uses_start_directory_and_closes(client, tmp_path):
    folder = tmp_path / "nested"
    folder.mkdir()
    path = folder / "run.md"
    path.write_text(
        "```python\nimport os\nprint(os.getcwd())\nos.chdir('nested')\n```\n"
    )
    item = client.post("/api/paths/open", json={"path": str(path)}).json()["document"]
    doc = client.get(f"{item['base']}/api/document").json()
    executed = client.post(f"{item['base']}/api/execute", json={**doc, "block": 0})
    assert executed.status_code == 200
    assert str(tmp_path) in executed.json()["source"]
    response = client.post("/api/paths/open", json={"path": "./start.md"})
    assert response.status_code == 200
    assert response.json()["document"]["path"] == str(tmp_path / "start.md")


def test_directory_creates_a_real_session_and_reuses_it(client, tmp_path, monkeypatch):
    from imd.session_api import close_session, list_sessions

    folder = tmp_path / "new directory"
    folder.mkdir()
    monkeypatch.setenv("IMD_SESSIONS_DIR", str(sessions.SESSIONS_DIR))
    calls = []
    monkeypatch.setattr(
        browser, "open_url", lambda url: calls.append(url) or {"action": "opened"}
    )
    created = []
    try:
        response = client.post("/api/paths/open", json={"path": str(folder)})
        created = list_sessions()
        assert response.status_code == 200, response.text
        assert len(created) == 1
        entry = created[0]
        assert entry.cwd == str(folder.resolve())
        path = Path(entry.paths[0])
        assert path.is_file()
        assert path.read_text() == ""
        assert (
            path.parent == (Path("/tmp") / folder.resolve().relative_to("/")).resolve()
        )
        response = client.post("/api/paths/open", json={"path": str(folder)})
        assert response.status_code == 200
        assert calls == [entry.url, entry.url]
        assert len(list_sessions()) == 1
    finally:
        for entry in created:
            close_session(entry.port)
            for path in entry.paths:
                Path(path).unlink(missing_ok=True)
