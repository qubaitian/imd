"""The local document API and session WebSocket."""

import asyncio
import ipaddress
import json
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote, urlsplit

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from imd.outputs import output_block, replace_output
from imd.sessions import Sessions
from imd.workspace import Conflict, Workspace


class SaveDocument(BaseModel):
    path: str
    content: str = Field(max_length=4_000_000)
    revision: str


class ConsoleMessage(BaseModel):
    type: str
    id: str = Field(default="", max_length=100)
    code: str = Field(default="", max_length=256_000)
    language: str = "xonsh"
    data: str = Field(default="", max_length=8192)
    columns: int = Field(default=80, ge=2, le=500)
    rows: int = Field(default=24, ge=2, le=200)
    block_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{6,32}$")
    content: str | None = Field(default=None, max_length=4_000_000)
    revision: str | None = None


def local_host(host: str) -> bool:
    try:
        hostname = urlsplit(f"http://{host}").hostname
        return hostname == "localhost" or ipaddress.ip_address(hostname).is_loopback
    except (ValueError, TypeError):
        return False


def create_app(root: Path | None = None) -> FastAPI:
    default_root = (root or Path.cwd()).resolve()
    sessions = Sessions()
    runs: set[asyncio.Task] = set()

    @asynccontextmanager
    async def lifespan(app):
        yield
        await sessions.close()
        for task in tuple(runs):
            task.cancel()
        await asyncio.gather(*runs, return_exceptions=True)

    app = FastAPI(lifespan=lifespan)

    @app.middleware("http")
    async def check_browser(request: Request, call_next):
        host = request.headers.get("host", "")
        if not local_host(host):
            return JSONResponse({"detail": "Use a loopback host."}, status_code=400)
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{host}":
            return JSONResponse({"detail": "Use the same browser origin."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
        return response

    def open_workspace(directory: str | None = None):
        try:
            root = Path(directory) if directory is not None else default_root
            if not root.is_absolute():
                raise ValueError("Use an absolute workspace directory.")
            workspace = Workspace(root)
            if not workspace.root.is_dir():
                raise FileNotFoundError(root)
            return workspace
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        except FileNotFoundError as error:
            raise HTTPException(404, "Workspace directory not found.") from error
        except OSError as error:
            raise HTTPException(400, "Cannot open this workspace.") from error

    def document_path(name, workspace):
        try:
            path = workspace.path(name)
            if not path.is_file():
                raise FileNotFoundError(name)
            return path
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        except FileNotFoundError as error:
            raise HTTPException(404, "Document not found.") from error

    @app.get("/api/documents")
    async def list_documents(workspace: str | None = None):
        return {"documents": open_workspace(workspace).list()}

    @app.get("/api/document")
    async def read_document(path: str, workspace: str | None = None):
        workspace = open_workspace(workspace)
        document_path(path, workspace)
        try:
            return workspace.read(path)
        except (OSError, UnicodeError) as error:
            raise HTTPException(400, "Cannot read this document as UTF-8.") from error

    @app.put("/api/document")
    async def save_document(document: SaveDocument, workspace: str | None = None):
        workspace = open_workspace(workspace)
        document_path(document.path, workspace)
        try:
            saved = workspace.save(document.path, document.content, document.revision)
            session = await sessions.get(document_path(document.path, workspace))
            session.publish({"type": "document", "document": saved})
            return saved
        except Conflict as error:
            raise HTTPException(409, str(error)) from error
        except (OSError, UnicodeError) as error:
            raise HTTPException(400, "Cannot save this document.") from error

    @app.post("/api/session/reset")
    async def reset_session(path: str, workspace: str | None = None):
        workspace = open_workspace(workspace)
        session = await sessions.reset(document_path(path, workspace))
        return session.snapshot()

    @app.websocket("/api/session")
    async def console(socket: WebSocket, path: str, workspace: str | None = None):
        host = socket.headers.get("host", "")
        scheme = "https" if socket.url.scheme == "wss" else "http"
        if not local_host(host) or socket.headers.get("origin") != f"{scheme}://{host}":
            await socket.close(code=1008)
            return
        try:
            workspace = open_workspace(workspace)
            document = document_path(path, workspace)
        except HTTPException as error:
            await socket.accept()
            await socket.close(code=1008, reason=f"{error.detail} Refresh the document list.")
            return
        await socket.accept()
        session = await sessions.get(document)
        events = session.subscribe()

        async def send_events():
            while True:
                event = await events.get()
                await socket.send_json(event)
                if event["type"] == "closed":
                    await socket.close(code=1012)
                    return

        async def run_code(code, run_id, block_id, language):
            try:
                result = await session.run(code, run_id, block_id, language=language)
            except RuntimeError as error:
                session.publish(
                    {"type": "error", "message": str(error), "id": run_id, "block_id": block_id}
                )
                return
            if block_id:
                try:
                    latest = workspace.read(path)
                    content = replace_output(
                        latest["content"], block_id, result["text"], code, language
                    )
                    saved = workspace.save(path, content, latest["revision"])
                    session.publish(
                        {"type": "document", "document": saved, "id": run_id, "block_id": block_id}
                    )
                except (ValueError, OSError, Conflict) as error:
                    session.publish(
                        {
                            "type": "save_error",
                            "message": str(error),
                            "id": run_id,
                            "block_id": block_id,
                            "text": result["text"],
                        }
                    )

        sender = asyncio.create_task(send_events())
        try:
            while True:
                try:
                    message = ConsoleMessage.model_validate(await socket.receive_json())
                except (ValidationError, json.JSONDecodeError):
                    events.put_nowait({"type": "error", "message": "Invalid console message."})
                    continue
                if message.type == "run":
                    if len(runs) >= 100:
                        events.put_nowait({"type": "error", "message": "Too many queued runs."})
                        continue
                    code = message.code
                    language = message.language
                    if message.block_id:
                        try:
                            if message.content is None or message.revision is None:
                                raise ValueError(
                                    "A marked run needs document content and revision."
                                )
                            block = output_block(message.content, message.block_id)
                            code, language = block["code"], block["language"]
                            saved = workspace.save(path, message.content, message.revision)
                            session.publish({"type": "document", "document": saved})
                        except (ValueError, OSError, Conflict) as error:
                            events.put_nowait(
                                {
                                    "type": "error",
                                    "message": str(error),
                                    "id": message.id,
                                    "block_id": message.block_id,
                                }
                            )
                            continue
                    task = asyncio.create_task(
                        run_code(code, message.id, message.block_id, language)
                    )
                    runs.add(task)
                    task.add_done_callback(runs.discard)
                elif message.type == "input":
                    session.write(message.data)
                elif message.type == "resize":
                    session.resize(message.columns, message.rows)
                elif message.type == "interrupt":
                    session.interrupt()
                else:
                    events.put_nowait({"type": "error", "message": "Unknown console message."})
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            session.unsubscribe(events)
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)

    package = Path(__file__).resolve().parent
    dist = package / "static"
    if not (dist / "index.html").is_file():
        dist = package.parent / "frontend" / "dist"
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/")
    async def home():
        return RedirectResponse(quote(str(default_root)))

    @app.get("/{directory:path}")
    async def open_directory(directory: str):
        workspace = open_workspace("/" + directory)
        try:
            workspace.open_default()
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        except (OSError, UnicodeError) as error:
            raise HTTPException(400, "Cannot open imd.md in this workspace.") from error
        if (dist / "index.html").is_file():
            return FileResponse(dist / "index.html")
        return JSONResponse(
            {"detail": "Build the frontend with npm run build in frontend/."}, status_code=503
        )

    return app
