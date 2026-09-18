import pytest
from fastapi.testclient import TestClient

from imd import sessions
from imd.app import create_app


@pytest.fixture
def panels(tmp_path, monkeypatch):
    for name in ("a.md", "b.md", "c.md"):
        (tmp_path / name).write_text(f"# {name}\n")
    saved = []
    monkeypatch.setattr(sessions, "update_paths", lambda token, paths: saved.append(paths))
    app = create_app(["a.md", "b.md", "c.md"], tmp_path, token="panels")
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer panels"
        yield client, saved


def test_order_survives_reads_and_keeps_document_routes(panels):
    client, saved = panels
    original = client.get("/api/session").json()["documents"]
    ordered = [original[2], original[0], original[1]]
    response = client.put("/api/session/order", json={"ids": [item["id"] for item in ordered]})
    assert response.status_code == 200
    assert response.json()["documents"] == ordered
    assert client.get("/api/session").json()["documents"] == ordered
    assert saved[-1] == [item["path"] for item in ordered]
    for item in ordered:
        assert client.get(item["base"] + "/api/document").json()["path"] == item["path"]


def test_repeated_file_panels_have_separate_ids_and_share_the_document(panels):
    client, _ = panels
    original = client.get("/api/session").json()["documents"]
    duplicate = client.post("/api/paths/open", json={"path": "a.md"}).json()["document"]
    assert duplicate["id"] != original[0]["id"]
    assert duplicate["base"] == original[0]["base"]
    ordered = [duplicate, original[1], original[0], original[2]]
    assert client.put("/api/session/order", json={"ids": [item["id"] for item in ordered]}).status_code == 200
    assert client.get("/api/session").json()["documents"] == ordered
    added = client.post("/api/paths/open", json={"path": "b.md"}).json()["document"]
    assert client.get("/api/session").json()["documents"] == [*ordered, added]


@pytest.mark.parametrize("invalid", ["missing", "duplicate", "unknown"])
def test_invalid_order_keeps_every_panel(panels, invalid):
    client, saved = panels
    original = client.get("/api/session").json()["documents"]
    ids = [item["id"] for item in original]
    if invalid == "missing":
        ids.pop()
    elif invalid == "duplicate":
        ids[1] = ids[0]
    else:
        ids[1] = "unknown"
    response = client.put("/api/session/order", json={"ids": ids})
    assert response.status_code == 409
    assert client.get("/api/session").json()["documents"] == original
    assert saved == []


def test_failed_save_keeps_the_order(panels, monkeypatch):
    client, _ = panels
    original = client.get("/api/session").json()["documents"]

    def fail(token, paths):
        raise OSError("Cannot save panel order.")

    monkeypatch.setattr(sessions, "update_paths", fail)
    response = client.put("/api/session/order", json={"ids": [item["id"] for item in reversed(original)]})
    assert response.status_code == 503
    assert client.get("/api/session").json()["documents"] == original


def test_order_requires_the_session_token(panels):
    client, _ = panels
    client.headers.clear()
    assert client.put("/api/session/order", json={"ids": []}).status_code == 401
