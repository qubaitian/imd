import socket
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from imd.app import create_app
from imd._server import LISTEN_HOST, session_url


def test_session_accepts_any_host(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("# host\n", encoding="utf-8")
    app = create_app(path.name, tmp_path, token="host-test")
    with TestClient(app, base_url="http://example.com") as client:
        client.headers["Authorization"] = "Bearer host-test"
        assert client.get("/api/session").status_code == 200
        assert client.get("/api/document").status_code == 200


def test_listen_host_is_all_interfaces():
    assert LISTEN_HOST == "0.0.0.0"
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind((LISTEN_HOST, 0))
        host, port = listener.getsockname()
    finally:
        listener.close()
    assert host == "0.0.0.0"
    assert 1 <= port <= 65535


def test_session_url_uses_all_interfaces():
    url = session_url(8080, "secret")
    parts = urlsplit(url)
    assert parts.scheme == "http"
    assert parts.hostname == "0.0.0.0"
    assert parts.port == 8080
    assert parts.fragment == "token=secret"
