import asyncio
import json
import secrets
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from queue import Empty, Queue
from threading import RLock, Thread

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .document import Conflict, Document, blocks, with_output
from .kernel import Kernel

STATIC = Path(__file__).parent / "static"


class SaveRequest(BaseModel):
    source: str
    revision: str


class ExecuteRequest(SaveRequest):
    block: int


class ParseRequest(BaseModel):
    source: str


class InputRequest(BaseModel):
    request: str
    value: str


class CompleteRequest(BaseModel):
    code: str
    cursor: int


def _document_app(filename: str | None, cwd: Path, token: str, base: str) -> FastAPI:
    document = Document.open(filename, cwd)
    kernel = Kernel(cwd)
    lock = RLock()
    active_run = None
    session_token = token or secrets.token_urlsafe(32)
    asset_cookie = f"imd-assets-{session_token[:12]}"

    @asynccontextmanager
    async def lifespan(app):
        yield
        kernel.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.token = session_token
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    def authorize(authorization: str = Header(default="")):
        if not secrets.compare_digest(authorization, f"Bearer {session_token}"):
            raise HTTPException(
                401, "Open the document with the full address that imd shows at start."
            )

    def save(source, revision):
        try:
            return document.save(source, revision)
        except Conflict as error:
            raise HTTPException(
                409, {"message": str(error), "source": source}
            ) from error

    @app.get("/api/document", dependencies=[Depends(authorize)])
    def read_document(response: Response):
        with lock:
            response.set_cookie(
                asset_cookie,
                session_token,
                httponly=True,
                samesite="strict",
                path=f"{base}/api/assets",
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
        with lock:
            if active_run is not None:
                raise HTTPException(409, "Wait for execution to finish before saving.")
            return save(request.source, request.revision)

    @app.post("/api/parse", dependencies=[Depends(authorize)])
    def parse_document(request: ParseRequest):
        return {"blocks": blocks(request.source)}

    @app.post("/api/complete", dependencies=[Depends(authorize)])
    def complete(request: CompleteRequest):
        if not 0 <= request.cursor <= len(request.code):
            raise HTTPException(422, "The cursor must be inside the code.")
        with lock:
            if active_run is not None:
                return {
                    "matches": [],
                    "cursor_start": request.cursor,
                    "cursor_end": request.cursor,
                }
        return kernel.complete(request.code, request.cursor)

    @app.post("/api/execute", dependencies=[Depends(authorize)])
    def execute(request: ExecuteRequest, accept: str = Header(default="")):
        nonlocal active_run
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
            saved = save(request.source, request.revision)
            run_id = secrets.token_urlsafe(24)
            active_run = run_id

        def finish(emit=None):
            nonlocal active_run
            try:
                output = kernel.execute(items[request.block]["code"], emit)
                result = with_output(request.source, request.block, output)
                with lock:
                    return save(result, saved["revision"])
            except HTTPException:
                raise
            except Exception as error:
                raise HTTPException(500, f"Execution failed: {error}") from error
            finally:
                with lock:
                    active_run = None

        if "application/x-ndjson" not in accept:
            return finish()

        events = Queue()

        def work():
            try:
                events.put({"type": "done", "document": finish(events.put)})
            except HTTPException as error:
                events.put({"type": "error", "detail": error.detail})

        async def stream():
            try:
                Thread(target=work, name="imd-execution", daemon=True).start()
                yield json.dumps({"type": "start", "id": run_id}) + "\n"
                while True:
                    try:
                        event = events.get_nowait()
                    except Empty:
                        await asyncio.sleep(0.02)
                        continue
                    yield json.dumps(event) + "\n"
                    if event["type"] in {"done", "error"}:
                        break
            finally:
                with lock:
                    if active_run == run_id:
                        kernel.interrupt()

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
            try:
                kernel.input(request.request, request.value)
            except ValueError as error:
                raise HTTPException(409, str(error)) from error
            return {"ok": True}

    @app.post("/api/execute/{run_id}/stop", dependencies=[Depends(authorize)])
    def stop(run_id: str):
        with lock:
            if active_run != run_id:
                raise HTTPException(409, "This execution is no longer active.")
            kernel.interrupt()
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
    filenames = filename if isinstance(filename, list) else [filename]
    if not 1 <= len(filenames) <= 2:
        raise ValueError("Give one or two file paths.")
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

    @asynccontextmanager
    async def lifespan(app):
        async with AsyncExitStack() as stack:
            for child in children:
                await stack.enter_async_context(child.router.lifespan_context(child))
            yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.token = session_token
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.get("/api/session")
    def read_session(authorization: str = Header(default="")):
        if not secrets.compare_digest(authorization, f"Bearer {session_token}"):
            raise HTTPException(401, "Open the full session URL.")
        return {"documents": documents}

    for item, child in reversed(list(zip(documents, children))):
        app.mount(item["base"], child)
    return app
