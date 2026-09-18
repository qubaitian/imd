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

        source = "# Smoke test\n\n```python\n1 + 1\n```\n"
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
            "markdown",
        ]
        assert blocks(result)[-1]["raw"] == "2\n"
        assert path.read_text(encoding="utf-8") == result
