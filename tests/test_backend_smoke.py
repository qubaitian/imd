import json
from threading import Event, Thread
from time import monotonic, sleep

import httpx
import uvicorn
from fastapi.testclient import TestClient

from imd.app import create_app
from imd.document import blocks
from imd.kernel import Kernel


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


def test_interrupt_stops_a_flooding_shell_command(tmp_path):
    script = tmp_path / "flood.py"
    script.write_text(
        "import time\n"
        "while True:\n"
        "    print('x' * 200, flush=True)\n"
        "    time.sleep(0.001)\n",
        encoding="utf-8",
    )
    kernel = Kernel(tmp_path)
    worker = None
    try:
        started = Event()
        result = []
        errors = []

        def run():
            try:
                result.append(
                    kernel.execute(
                        f"!python {script}",
                        lambda event: (
                            started.set() if event.get("type") == "output" else None
                        ),
                    )
                )
            except Exception as exc:
                errors.append(exc)

        worker = Thread(target=run)
        worker.start()
        assert started.wait(30)
        assert worker.is_alive()
        kernel.manager.interrupt_kernel = lambda: None
        began = monotonic()
        kernel.interrupt()
        worker.join(timeout=15)
        assert not errors
        assert not worker.is_alive()
        assert monotonic() - began < 10
        assert result
    finally:
        kernel.interrupt()
        if worker is not None:
            worker.join(timeout=5)
        kernel.close()


def test_stop_endpoint_interrupts_streaming_shell_command(tmp_path):
    script = tmp_path / "flood.py"
    script.write_text(
        "import time\n"
        "while True:\n"
        "    print('x' * 200, flush=True)\n"
        "    time.sleep(0.001)\n",
        encoding="utf-8",
    )
    path = tmp_path / "doc.md"
    path.write_text(f"```python\n!python {script}\n```\n", encoding="utf-8")
    app = create_app(path.name, tmp_path, token="stop-test")
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error")
    )
    thread = Thread(target=server.run, daemon=True)
    thread.start()
    deadline = monotonic() + 10
    while not server.started and monotonic() < deadline:
        sleep(0.05)
    assert server.started
    port = server.servers[0].sockets[0].getsockname()[1]
    headers = {
        "Authorization": "Bearer stop-test",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", timeout=30.0
        ) as stream_client:
            document = stream_client.get("/api/document", headers=headers).json()
            with (
                httpx.Client(
                    base_url=f"http://127.0.0.1:{port}", timeout=30.0
                ) as stop_client,
                stream_client.stream(
                    "POST",
                    "/api/execute",
                    headers={**headers, "Accept": "application/x-ndjson"},
                    json={
                        "source": document["source"],
                        "revision": document["revision"],
                        "block": 0,
                    },
                ) as response,
            ):
                run_id = None
                began = monotonic()
                stopped = False
                done = False
                for line in response.iter_lines():
                    if not line:
                        continue
                    event = json.loads(line)
                    if event["type"] == "start":
                        run_id = event["id"]
                    elif event["type"] == "output" and run_id and not stopped:
                        stop = stop_client.post(
                            f"/api/execute/{run_id}/stop", headers=headers
                        )
                        assert stop.status_code == 200
                        stopped = True
                        began = monotonic()
                    elif event["type"] in {"done", "error"}:
                        done = True
                        break
                assert stopped
                assert done
                assert monotonic() - began < 10
    finally:
        server.should_exit = True
        thread.join(timeout=5)
