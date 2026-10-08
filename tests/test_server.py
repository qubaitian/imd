from fastapi.testclient import TestClient

from imd.server import create_app


def test_document_api_and_origin_checks(tmp_path):
    (tmp_path / "guide.md").write_text("# Guide\n")
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        assert client.get("/api/documents").json() == {"documents": ["guide.md"]}
        document = client.get("/api/document", params={"path": "guide.md"}).json()
        response = client.put("/api/document", json={**document, "content": "# Saved\n"})
        assert response.status_code == 200
        assert client.put("/api/document", json=document).status_code == 409
        assert client.get("/api/document", params={"path": "../outside.md"}).status_code == 400
        assert client.get("/api/documents", headers={"host": "evil.example"}).status_code == 400
        assert (
            client.put(
                "/api/document", json=response.json(), headers={"origin": "https://evil.example"}
            ).status_code
            == 403
        )


def receive_until(socket, kind):
    messages = []
    while True:
        message = socket.receive_json()
        messages.append(message)
        if message["type"] == kind:
            return messages


def test_websocket_runs_code_and_keeps_state_after_reconnecting(tmp_path):
    (tmp_path / "guide.md").write_text("# Guide\n")
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        with client.websocket_connect(
            "ws://127.0.0.1/api/session?path=guide.md", headers={"origin": "http://127.0.0.1"}
        ) as socket:
            assert socket.receive_json()["type"] == "snapshot"
            socket.send_json({"type": "run", "id": "one", "code": "value = 42\nprint('first run')"})
            messages = receive_until(socket, "done")
            assert messages[-1]["status"] == "ok"
            assert "first run" in "".join(m.get("data", "") for m in messages)
        with client.websocket_connect(
            "ws://127.0.0.1/api/session?path=guide.md", headers={"origin": "http://127.0.0.1"}
        ) as socket:
            assert "first run" in socket.receive_json()["output"]
            socket.send_json({"type": "run", "id": "two", "code": "print(value)"})
            messages = receive_until(socket, "done")
            assert "42" in "".join(m.get("data", "") for m in messages)
            assert messages[-1]["status"] == "ok"


def test_websocket_requires_a_same_origin_browser(tmp_path):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    (tmp_path / "guide.md").write_text("# Guide\n")
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        for headers in [{}, {"origin": "https://evil.example"}]:
            with (
                pytest.raises(WebSocketDisconnect),
                client.websocket_connect(
                    "ws://127.0.0.1/api/session?path=guide.md", headers=headers
                ),
            ):
                pass


def test_reset_closes_old_connections_and_starts_a_fresh_session(tmp_path):
    (tmp_path / "guide.md").write_text("# Guide\n")
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        with client.websocket_connect(
            "ws://127.0.0.1/api/session?path=guide.md", headers={"origin": "http://127.0.0.1"}
        ) as socket:
            socket.receive_json()
            socket.send_json(
                {"type": "run", "id": "before", "code": "value = 42\nprint('before reset')"}
            )
            receive_until(socket, "done")
            response = client.post("/api/session/reset", params={"path": "guide.md"})
            assert response.status_code == 200
            assert response.json()["state"] == "ready"
            assert receive_until(socket, "closed")[-1]["type"] == "closed"
        with client.websocket_connect(
            "ws://127.0.0.1/api/session?path=guide.md", headers={"origin": "http://127.0.0.1"}
        ) as socket:
            assert "before reset" not in socket.receive_json()["output"]
            socket.send_json(
                {
                    "type": "run",
                    "id": "after",
                    "code": "print('fresh=' + str('value' not in globals()))",
                }
            )
            messages = receive_until(socket, "done")
            assert "fresh=True" in "".join(m.get("data", "") for m in messages)


def test_two_browser_tabs_share_a_document_session(tmp_path):
    (tmp_path / "guide.md").write_text("# Guide\n")
    with (
        TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client,
        client.websocket_connect(
            "ws://127.0.0.1/api/session?path=guide.md", headers={"origin": "http://127.0.0.1"}
        ) as first,
        client.websocket_connect(
            "ws://127.0.0.1/api/session?path=guide.md", headers={"origin": "http://127.0.0.1"}
        ) as second,
    ):
        first.receive_json()
        second.receive_json()
        first.send_json({"type": "run", "id": "first", "code": "value = 42"})
        receive_until(first, "done")
        receive_until(second, "done")
        second.send_json({"type": "run", "id": "second", "code": "print('shared=' + str(value))"})
        for socket in [first, second]:
            messages = receive_until(socket, "done")
            assert "shared=42" in "".join(m.get("data", "") for m in messages)
