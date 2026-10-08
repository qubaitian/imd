import time

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


def test_marked_run_saves_plain_output_and_replaces_it_on_the_next_run(tmp_path):
    source = "```py\nprint('saved output')\n```\n\n<!-- abc123 -->\n```txt\nold output\n```\n"
    file = tmp_path / "guide.md"
    file.write_text(source)
    with (
        TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client,
        client.websocket_connect(
            "ws://127.0.0.1/api/session?path=guide.md", headers={"origin": "http://127.0.0.1"}
        ) as socket,
    ):
        socket.receive_json()
        for run_id in ["first", "second"]:
            document = client.get("/api/document", params={"path": "guide.md"}).json()
            socket.send_json({"type": "run", "id": run_id, "block_id": "abc123", **document})
            receive_until(socket, "done")
            saved = receive_until(socket, "document")[-1]
            assert saved["document"]["content"] == file.read_text()
            assert "```txt\nsaved output\n```" in file.read_text()
            assert file.read_text().count("<!-- abc123 -->") == 1


def test_output_save_preserves_edits_made_while_running(tmp_path):
    source = "```py\nanswer = input('Ready? ')\nprint(answer)\n```\n<!-- abc123 -->\n```txt\n```\n\nOriginal paragraph.\n"
    file = tmp_path / "guide.md"
    file.write_text(source)
    with (
        TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client,
        client.websocket_connect(
            "ws://127.0.0.1/api/session?path=guide.md", headers={"origin": "http://127.0.0.1"}
        ) as socket,
    ):
        socket.receive_json()
        document = client.get("/api/document", params={"path": "guide.md"}).json()
        socket.send_json({"type": "run", "id": "one", "block_id": "abc123", **document})
        receive_until(socket, "running")
        output = ""
        while "Ready? " not in output:
            output += socket.receive_json().get("data", "")
        document = client.get("/api/document", params={"path": "guide.md"}).json()
        response = client.put(
            "/api/document",
            json={
                **document,
                "content": document["content"].replace("Original paragraph.", "Edited paragraph."),
            },
        )
        assert response.status_code == 200
        socket.send_json({"type": "input", "data": "yes\n"})
        receive_until(socket, "done")
        receive_until(socket, "document")
        assert "Edited paragraph." in file.read_text()
        assert "Ready? yes\nyes\n" in file.read_text()


def test_output_is_saved_after_the_browser_disconnects(tmp_path):
    source = "```py\nimport time\nprint('started', flush=True)\ntime.sleep(0.15)\nprint('finished without browser')\n```\n<!-- abc123 -->\n```txt\n```\n"
    file = tmp_path / "guide.md"
    file.write_text(source)
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        with client.websocket_connect(
            "ws://127.0.0.1/api/session?path=guide.md", headers={"origin": "http://127.0.0.1"}
        ) as socket:
            socket.receive_json()
            document = client.get("/api/document", params={"path": "guide.md"}).json()
            socket.send_json({"type": "run", "id": "one", "block_id": "abc123", **document})
            output = ""
            while "started" not in output:
                output += socket.receive_json().get("data", "")
        deadline = time.monotonic() + 5
        while "```txt\nstarted\nfinished without browser\n```" not in file.read_text():
            assert time.monotonic() < deadline
            time.sleep(0.01)


def test_changed_code_keeps_the_result_available_without_overwriting_the_file(tmp_path):
    source = "```py\nanswer = input('Ready? ')\nprint(answer)\n```\n<!-- abc123 -->\n```txt\n```\n"
    file = tmp_path / "guide.md"
    file.write_text(source)
    with (
        TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client,
        client.websocket_connect(
            "ws://127.0.0.1/api/session?path=guide.md", headers={"origin": "http://127.0.0.1"}
        ) as socket,
    ):
        socket.receive_json()
        document = client.get("/api/document", params={"path": "guide.md"}).json()
        socket.send_json({"type": "run", "id": "one", "block_id": "abc123", **document})
        output = ""
        while "Ready? " not in output:
            output += socket.receive_json().get("data", "")
        changed = source.replace("print(answer)", "print('changed code')")
        file.write_text(changed)
        socket.send_json({"type": "input", "data": "y\n"})
        receive_until(socket, "done")
        error = receive_until(socket, "save_error")[-1]
        assert "code changed" in error["message"]
        assert "Ready? y" in error["text"]
        assert file.read_text() == changed
