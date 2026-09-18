import asyncio
import json
import secrets
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from queue import Empty, Queue
from threading import RLock, Thread

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import browser, sessions
from . import paths as local_paths
from .document import Conflict, Document, blocks, with_output
from .shell import Shell, check_language

STATIC = Path(__file__).parent / "static"


class _LiveEvents:
    """Join the terminal data that arrives between two reads of the stream."""

    def __init__(self):
        self._queue = Queue()
        self._data = ""
        self._lock = RLock()

    def data(self, text):
        with self._lock:
            self._data += text

    def put(self, event):
        self._queue.put(event)

    def take(self):
        with self._lock:
            if self._data:
                event = {"type": "data", "text": self._data}
                self._data = ""
                return event
        try:
            return self._queue.get_nowait()
        except Empty:
            return None


class SaveRequest(BaseModel):
    source: str
    revision: str


class ExecuteRequest(SaveRequest):
    block: int


class ParseRequest(BaseModel):
    source: str


class InputRequest(BaseModel):
    value: str


class BrowserRequest(BaseModel):
    url: str


class PathRequest(BaseModel):
    path: str


def _document_app(
    filename: str | None, cwd: Path, token: str, base: str, readonly: bool = False
) -> FastAPI:
    document = Document.open(filename, cwd)
    lock = RLock()
    active_run = None
    session_token = token or secrets.token_urlsafe(32)
    shell = Shell(cwd, session_token)
    asset_cookie = f"imd-assets-{session_token[:12]}"

    @asynccontextmanager
    async def lifespan(app):
        yield
        await asyncio.to_thread(shell.close)

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.token = session_token

    def authorize(authorization: str = Header(default="")):
        if not secrets.compare_digest(authorization, f"Bearer {session_token}"):
            raise HTTPException(
                401, "Open the document with the full address that imd shows at start."
            )

    def save(source, revision):
        try:
            return document.save(source, revision)
        except Conflict as exc:
            raise HTTPException(409, str(exc)) from exc

    def require_editable():
        if readonly:
            raise HTTPException(403, "This file is read-only.")

    @app.post("/api/browser/open", dependencies=[Depends(authorize)])
    def open_browser(request: BrowserRequest):
        try:
            return browser.open_url(request.url)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.get("/api/document", dependencies=[Depends(authorize)])
    def read_document(request: Request, response: Response):
        with lock:
            if readonly:
                return {
                    "name": document.path.name,
                    "path": str(document.path),
                    "source": local_paths.read_text(document.path),
                    "readonly": True,
                    "revision": "",
                }
            response.set_cookie(
                asset_cookie,
                session_token,
                httponly=True,
                samesite="strict",
                path=f"{request.scope.get('root_path', '')}/api/assets",
            )
            return document.read()

    @app.get("/api/assets/{asset_path:path}")
    def local_asset(
        asset_path: str, imd_assets: str = Cookie(default="", alias=asset_cookie)
    ):
        if not secrets.compare_digest(imd_assets, session_token):
            raise HTTPException(401, "Open the document first.")
        path = (document.path.parent / asset_path).resolve()
        allowed = {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".svg",
            ".avif",
            ".ico",
            ".bmp",
        }
        if (
            not path.is_relative_to(document.path.parent)
            or path.suffix.lower() not in allowed
            or not path.is_file()
        ):
            raise HTTPException(404, "The image does not exist.")
        return FileResponse(
            path,
            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache"},
        )

    @app.put("/api/document", dependencies=[Depends(authorize)])
    def save_document(request: SaveRequest):
        require_editable()
        with lock:
            if active_run is not None:
                raise HTTPException(409, "Wait for execution to finish before saving.")
            return save(request.source, request.revision)

    @app.post("/api/parse", dependencies=[Depends(authorize)])
    def parse_document(request: ParseRequest):
        return {"blocks": blocks(request.source)}

    @app.post("/api/execute", dependencies=[Depends(authorize)])
    def execute(request: ExecuteRequest, accept: str = Header(default="")):
        nonlocal active_run
        require_editable()
        with lock:
            if active_run is not None:
                raise HTTPException(409, "A code block is already running.")
            items = blocks(request.source)
            if (
                request.block < 0
                or request.block >= len(items)
                or items[request.block]["kind"] != "code"
            ):
                raise HTTPException(400, "Select a code block.")
            try:
                language = check_language(items[request.block]["language"])
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            saved = save(request.source, request.revision)
            run_id = secrets.token_urlsafe(24)
            active_run = run_id

        def finish(emit=None):
            nonlocal active_run
            try:
                output = shell.execute(items[request.block]["code"], language, emit)
                result = with_output(request.source, request.block, output)
                with lock:
                    return save(result, saved["revision"])
            finally:
                with lock:
                    active_run = None

        if "application/x-ndjson" not in accept:
            return finish()

        events = _LiveEvents()

        def work():
            try:
                events.put({"type": "done", "document": finish(events.data)})
            except Exception as exc:
                events.put({"type": "error", "detail": str(exc)})

        async def stream():
            worker = Thread(target=work, name="imd-execution", daemon=True)
            worker.start()
            try:
                yield json.dumps({"type": "start", "id": run_id}) + "\n"
                while True:
                    event = events.take()
                    if event is not None:
                        yield json.dumps(event) + "\n"
                        await asyncio.sleep(0)
                        if event["type"] in {"done", "error"}:
                            break
                    elif worker.is_alive():
                        await asyncio.sleep(0.02)
                    else:
                        break
            finally:
                with lock:
                    if active_run == run_id:
                        shell.interrupt()

        return StreamingResponse(
            stream(),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/execute/{run_id}/input", dependencies=[Depends(authorize)])
    def send_input(run_id: str, request: InputRequest):
        with lock:
            if active_run != run_id:
                raise HTTPException(409, "This execution is no longer active.")
            shell.send(request.value)
            return {"ok": True}

    @app.post("/api/execute/{run_id}/stop", dependencies=[Depends(authorize)])
    def stop(run_id: str):
        with lock:
            if active_run != run_id:
                raise HTTPException(409, "This execution is no longer active.")
            shell.interrupt()
            return {"ok": True}

    @app.post("/api/execute/{run_id}/kill", dependencies=[Depends(authorize)])
    def kill(run_id: str):
        with lock:
            if active_run != run_id:
                raise HTTPException(409, "This execution is no longer active.")
            shell.kill()
            return {"ok": True}

    @app.get("/")
    def index():
        if not (STATIC / "index.html").is_file():
            raise HTTPException(
                503, "Run npm ci and npm run build in the web directory."
            )
        return FileResponse(
            STATIC / "index.html", headers={"Cache-Control": "no-store"}
        )

    if (STATIC / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")
    return app


def create_app(
    filename: str | list[str] | None, cwd: Path, token: str | None = None
) -> FastAPI:
    cwd = cwd.resolve()
    filenames = filename if isinstance(filename, list) else [filename]
    if not filenames:
        raise ValueError("Give at least one file path.")
    paths = [str((cwd / (name or "IMD.md")).resolve()) for name in filenames]
    if len(set(paths)) != len(paths):
        raise ValueError("Give different file paths.")
    for path in paths:
        if not Path(path).parent.is_dir():
            raise ValueError("The directory of each file must exist.")
        if Path(path).exists() and not Path(path).is_file():
            raise ValueError("Each path must refer to a file.")
    session_token = token or secrets.token_urlsafe(32)
    documents = [
        {"path": path, "base": "" if index == 0 else f"/documents/{index}"}
        for index, path in enumerate(paths)
    ]
    children = [
        _document_app(item["path"], cwd, session_token, item["base"])
        for item in documents
    ]
    opened = {item["path"]: item for item in documents}
    document_lock = asyncio.Lock()
    stack = AsyncExitStack()

    @asynccontextmanager
    async def lifespan(app):
        async with stack:
            for child in children:
                await stack.enter_async_context(child.router.lifespan_context(child))
            yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.token = session_token

    def authorize(authorization: str = Header(default="")):
        if not secrets.compare_digest(authorization, f"Bearer {session_token}"):
            raise HTTPException(401, "Open the full session URL.")

    @app.get("/api/session", dependencies=[Depends(authorize)])
    def read_session():
        return {"documents": documents, "cwd": str(cwd)}

    @app.post("/api/paths/open", dependencies=[Depends(authorize)])
    async def open_path(request: PathRequest):
        try:
            path = await asyncio.to_thread(local_paths.resolve_path, request.path, cwd)
            if path.is_dir():
                return await asyncio.to_thread(local_paths.open_directory, path)
            async with document_lock:
                item = opened.get(str(path))
                if item is None:
                    item = {
                        "path": str(path),
                        "base": f"/documents/{len(opened)}",
                        "readonly": path.suffix.lower() not in {".md", ".markdown"},
                    }
                    child = _document_app(
                        str(path), cwd, session_token, item["base"], item["readonly"]
                    )
                    await stack.enter_async_context(
                        child.router.lifespan_context(child)
                    )
                    app.mount(item["base"], child)
                    route = app.router.routes.pop()
                    app.router.routes.insert(app.router.routes.index(root_mount), route)
                    opened[str(path)] = item
                documents.append(item)
                await asyncio.to_thread(
                    sessions.update_paths,
                    session_token,
                    [entry["path"] for entry in documents],
                )
                return {"document": item}
        except FileNotFoundError as exc:
            raise HTTPException(404, "The path does not exist.") from exc
        except (ValueError, OSError) as exc:
            raise HTTPException(400, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc

    for item, child in reversed(list(zip(documents, children))):
        app.mount(item["base"], child)
    root_mount = app.router.routes[-1]
    return app
