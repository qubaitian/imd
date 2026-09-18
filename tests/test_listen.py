from fastapi.testclient import TestClient

from imd.app import create_app


def test_session_accepts_any_host(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("# host\n", encoding="utf-8")
    app = create_app(path.name, tmp_path, token="host-test")
    with TestClient(app, base_url="http://example.com") as client:
        client.headers["Authorization"] = "Bearer host-test"
        assert client.get("/api/session").status_code == 200
        assert client.get("/api/document").status_code == 200
