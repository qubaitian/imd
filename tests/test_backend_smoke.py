import json

import pytest
from fastapi.testclient import TestClient

from imd.app import create_app
from imd.document import blocks


def test_read_save_execute_document(tmp_path):
    path = tmp_path / "smoke.md"
    path.write_text("# Smoke test\n", encoding="utf-8")
    app = create_app(path.name, tmp_path, token="smoke-test")

    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers["Authorization"] = "Bearer smoke-test"

        response = client.get("/api/document")
        assert response.status_code == 200
        document = response.json()
        assert document["source"] == "# Smoke test\n"

        source = "# Smoke test\n\n```python\nprint(1 + 1)\n```\n"
        response = client.put(
            "/api/document",
            json={"source": source, "revision": document["revision"]},
        )
        assert response.status_code == 200
        document = response.json()
        assert document["source"] == source
        assert path.read_text(encoding="utf-8") == source

        response = client.post(
            "/api/execute",
            json={
                "source": document["source"],
                "revision": document["revision"],
                "block": 1,
            },
        )
        assert response.status_code == 200
        result = response.json()["source"]
        assert result.startswith(source + "\n<!-- imd:output:begin ")
        assert [item["kind"] for item in blocks(result)] == [
            "markdown",
            "code",
            "output",
            "text",
        ]
        assert blocks(result)[-1]["code"] == "2\n"
        assert path.read_text(encoding="utf-8") == result


@pytest.mark.parametrize("stream", [False, True])
def test_configured_command_renders_markdown_and_plain_fences_cannot_run(tmp_path, stream):
    app = create_app("report.md", tmp_path, token="test", markdown_commands=["printf"])
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer test"
        if stream:
            client.headers["Accept"] = "application/x-ndjson"
        document = client.get("/api/document").json()
        for code, expected in [("printf '# Report\\n'", "markdown"), ("printf '# Log\\n' | cat", "text")]:
            source = f"```shell\n{code}\n```\n"
            response = client.post("/api/execute", json={"source": source, "revision": document["revision"], "block": 0})
            assert response.status_code == 200
            document = json.loads(response.text.splitlines()[-1])["document"] if stream else response.json()
            assert document["blocks"][-1]["kind"] == expected
        response = client.post("/api/execute", json={"source": document["source"], "revision": document["revision"], "block": 2})
        assert response.status_code == 400
