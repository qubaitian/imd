import time

import pytest
from fastapi.testclient import TestClient

from imd.server import ConsoleMessage, create_app


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


def test_save_does_not_start_a_session(tmp_path, monkeypatch):
    from imd.sessions import Session

    async def fail_to_start(cls, cwd):
        raise RuntimeError("The session process ended.")

    monkeypatch.setattr(Session, "open", classmethod(fail_to_start))
    (tmp_path / "guide.md").write_text("# Guide\n")
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        document = client.get("/api/document", params={"path": "guide.md"}).json()
        response = client.put("/api/document", json={**document, "content": "# Saved\n"})
        assert response.status_code == 200
        assert (tmp_path / "guide.md").read_text() == "# Saved\n"


def test_save_notifies_an_open_session(tmp_path):
    (tmp_path / "guide.md").write_text("# Guide\n")
    with (
        TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client,
        client.websocket_connect(
            "ws://127.0.0.1/api/session?path=guide.md", headers={"origin": "http://127.0.0.1"}
        ) as socket,
    ):
        socket.receive_json()
        document = client.get("/api/document", params={"path": "guide.md"}).json()
        client.put("/api/document", json={**document, "content": "# Saved\n"})
        assert receive_until(socket, "document")[-1]["document"]["content"] == "# Saved\n"


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


def test_missing_document_closes_the_browser_connection_with_a_reason(tmp_path):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    with (
        TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client,
        client.websocket_connect(
            "ws://127.0.0.1/api/session?path=interaction.md",
            headers={"origin": "http://127.0.0.1"},
        ) as socket,
    ):
        with pytest.raises(WebSocketDisconnect) as failure:
            socket.receive_json()
        assert failure.value.code == 1008
        assert failure.value.reason == "Document not found. Refresh the document list."


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


@pytest.mark.parametrize("label", ["py", "", "js", "txt", "custom"])
def test_marked_run_saves_plain_output_and_replaces_it_on_the_next_run(tmp_path, label):
    source = f"```{label}\nprint('saved output')\n```\n\n<!-- abc123 -->\n```txt\nold output\n```\n"
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


def test_marked_agent_blocks_save_prompt_replies_after_sh_configuration(tmp_path):
    import shlex
    import sys

    script = tmp_path / "agent.py"
    script.write_text("import sys\nprint(sys.argv[1] + ':' + sys.argv[2].strip())\n")
    command = shlex.join([sys.executable, str(script)])
    source = (
        f"```sh\nimd set agent first {command} first\n"
        f"imd set agent continue {command} continue\n```\n"
        "<!-- abc123 -->\n```txt\n```\n"
        "```agent\n请审核代码\n```\n<!-- def456 -->\n```txt\n```\n"
        "```agent\nWhat did I ask?\n```\n<!-- aaa111 -->\n```txt\n```\n"
    )
    file = tmp_path / "guide.md"
    file.write_text(source)
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        for marker, expected in [
            ("abc123", "Agent commands configured for this session."),
            ("def456", "first:请审核代码"), ("aaa111", "continue:What did I ask?"),
        ]:
            with client.websocket_connect(
                "ws://127.0.0.1/api/session?path=guide.md",
                headers={"origin": "http://127.0.0.1"},
            ) as socket:
                socket.receive_json()
                document = client.get("/api/document", params={"path": "guide.md"}).json()
                socket.send_json({
                    "type": "run", "id": marker, "block_id": marker,
                    "code": "raise RuntimeError('do not trust client code')", **document,
                })
                result = receive_until(socket, "done")[-1]
                assert result["status"] == "ok", result["text"]
                assert result["text"] == expected + "\n"
                receive_until(socket, "document")
                assert f"```txt\n{expected}\n```" in file.read_text()


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


def test_directory_url_creates_and_preserves_the_default_document(tmp_path):
    from urllib.parse import quote

    directory = tmp_path / "notes with 空格"
    directory.mkdir()
    url = quote(str(directory))
    with TestClient(create_app(tmp_path), base_url="http://localhost:8000") as client:
        response = client.get(url)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        document = directory / "imd.md"
        assert document.read_text() == ""
        document.write_text("# Existing notes\n")
        assert client.get(url + "/").status_code == 200
        assert document.read_text() == "# Existing notes\n"
        assert client.get("/api/documents", params={"workspace": str(directory)}).json() == {
            "documents": ["imd.md"]
        }
        opened = client.get(
            "/api/document", params={"workspace": str(directory), "path": "imd.md"}
        ).json()
        assert opened["content"] == "# Existing notes\n"
        saved = client.put(
            "/api/document", params={"workspace": str(directory)},
            json={**opened, "content": "# Saved notes\n"},
        )
        assert saved.status_code == 200
        assert document.read_text() == "# Saved notes\n"


def test_directory_url_rejects_missing_directories_and_outside_default_document(tmp_path):
    (tmp_path / "outside.md").write_text("Keep me")
    directory = tmp_path / "notes"
    directory.mkdir()
    (directory / "imd.md").symlink_to(tmp_path / "outside.md")
    with TestClient(create_app(tmp_path), base_url="http://localhost:8000") as client:
        assert client.get(str(tmp_path / "missing")).status_code == 404
        assert not (tmp_path / "missing").exists()
        assert client.get(str(directory)).status_code == 400
        assert (tmp_path / "outside.md").read_text() == "Keep me"


def test_directory_sessions_are_separate(tmp_path):
    for name in ["first", "second"]:
        directory = tmp_path / name
        directory.mkdir()
        (directory / "imd.md").write_text("")
    with TestClient(create_app(tmp_path), base_url="http://localhost:8000") as client:
        from urllib.parse import urlencode

        for name in ["first", "second"]:
            query = urlencode({"workspace": str(tmp_path / name), "path": "imd.md"})
            with client.websocket_connect(
                f"ws://localhost:8000/api/session?{query}", headers={"origin": "http://localhost:8000"}
            ) as socket:
                socket.receive_json()
                code = "value = 42" if name == "first" else "print('isolated=' + str('value' not in globals()))"
                socket.send_json({"type": "run", "id": name, "code": code})
                messages = receive_until(socket, "done")
                if name == "second":
                    assert "isolated=True" in "".join(m.get("data", "") for m in messages)


@pytest.mark.parametrize("label", ["", "js", "txt", "custom"])
def test_console_accepts_any_code_label(label):
    message = ConsoleMessage.model_validate({"type": "run", "language": label})
    assert message.language == label


def test_browser_request_without_origin_does_not_create_the_default_document(tmp_path):
    directory = tmp_path / "notes"
    directory.mkdir()
    url = str(directory)
    browser = {"sec-fetch-site": "cross-site", "sec-fetch-mode": "no-cors", "sec-fetch-dest": "image"}
    with TestClient(create_app(tmp_path), base_url="http://localhost:8000") as client:
        response = client.get(url, headers=browser)
        assert response.status_code == 403
        assert not (directory / "imd.md").exists()
        opened = client.get(
            url,
            headers={"sec-fetch-site": "none", "sec-fetch-mode": "navigate", "sec-fetch-dest": "document"},
        )
        assert opened.status_code == 200
        assert (directory / "imd.md").read_text() == ""
        (directory / "imd.md").write_text("# Keep\n")
        again = client.get(url, headers=browser)
        assert again.status_code == 200
        assert (directory / "imd.md").read_text() == "# Keep\n"
        other = tmp_path / "other"
        other.mkdir()
        created = client.get(str(other), headers={"origin": "http://localhost:8000"})
        assert created.status_code == 200
        assert (other / "imd.md").read_text() == ""
