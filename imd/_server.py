"""Run all session routes on one HTTP port."""

import asyncio
import json
import logging
import os
import secrets
import socket
import sys
from dataclasses import asdict
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from . import sessions
from .app import STATIC, create_app
from .config import Config
from .session_api import create_temporary_document

logger = logging.getLogger(__name__)


class Service:
    def __init__(self, config: Config):
        self.config = config
        self.app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        self.active = {}
        self.lock = asyncio.Lock()
        self.server = uvicorn.Server(uvicorn.Config(self.app, log_level="warning"))

    async def dispatch(self, request):
        async with self.lock:
            operation = request["operation"]
            if operation == "ping":
                return None
            if operation == "list":
                return sessions.list_sessions()
            if operation == "open":
                if request["config"] != asdict(self.config):
                    raise ValueError(
                        "The configuration changes. Close all sessions, then run imd open."
                    )
                return await self.open(Path(request["cwd"]))
            if operation == "close":
                if request["number"] is None:
                    return await self.close_all(request.get("owner_token"))
                number = sessions.validate_number(request["number"])
                entry = self.active.get(number)
                if entry is None:
                    raise ValueError("The session does not exist.")
                if request.get("owner_token") == entry["app"].state.token:
                    raise ValueError("A session cannot close itself.")
                await self.close(number)
                last = not self.active
                if last:
                    self.server.should_exit = True
                return {"last": last}
            raise ValueError("The session operation does not exist.")

    async def open(self, cwd: Path):
        cwd = cwd.resolve(strict=True)
        if not cwd.is_dir():
            raise ValueError("The start directory must be a directory.")
        counter = sessions.SESSIONS_DIR / "next-session"
        number = int(counter.read_text()) if counter.exists() else 1
        counter.write_text(str(number + 1))
        path = create_temporary_document(cwd)
        token = secrets.token_urlsafe(32)
        app = create_app(
            str(path), cwd, token=token,
            markdown_commands=self.config.markdown_commands,
        )
        context = app.router.lifespan_context(app)
        try:
            await context.__aenter__()
            url = f"{self.config.public_url}/{number}/#token={token}"
            sessions.add_session([str(path)], url, os.getpid(), cwd, number)
        except BaseException:
            await context.__aexit__(None, None, None)
            path.unlink(missing_ok=True)
            raise
        self.app.mount(f"/{number}", app)
        self.active[number] = {
            "app": app,
            "context": context,
            "route": self.app.routes[-1],
        }
        return {"url": url, "cwd": str(cwd), "paths": [str(path)]}

    async def close(self, number):
        entry = self.active.pop(number)
        self.app.routes.remove(entry["route"])
        try:
            await entry["context"].__aexit__(None, None, None)
        finally:
            sessions.remove_session(number)

    async def close_all(self, owner_token):
        numbers = sorted(
            self.active,
            key=lambda number: self.active[number]["app"].state.token == owner_token,
        )
        errors = []
        for number in numbers:
            try:
                await self.close(number)
            except Exception as exc:
                logger.exception("Session %s fails to close.", number)
                errors.append(f"Session {number}: {exc}")
        self.server.should_exit = not self.active
        if errors:
            raise RuntimeError("\n".join(errors))
        return {"last": not self.active}

    async def control(self, reader, writer):
        try:
            request = json.loads(await reader.readline())
            result = await self.dispatch(request)
            response = {"result": result}
        except Exception as exc:
            logger.exception("The session operation fails.")
            response = {"error": str(exc), "kind": type(exc).__name__}
        try:
            writer.write(json.dumps(response).encode() + b"\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def run(self):
        if not (STATIC / "index.html").is_file():
            raise RuntimeError(
                "The frontend files are missing. Run npm ci and npm run build in the web directory."
            )
        control_path = sessions.SESSIONS_DIR / "control.sock"
        control = None
        family = socket.AF_INET6 if ":" in self.config.host else socket.AF_INET
        listener = socket.socket(family, socket.SOCK_STREAM)
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((self.config.host, self.config.port))
            control_path.unlink(missing_ok=True)
            control = await asyncio.start_unix_server(
                self.control, path=str(control_path)
            )
            control_path.chmod(0o600)
            task = asyncio.create_task(self.server.serve(sockets=[listener]))
            while not self.server.started:
                if task.done():
                    await task
                    raise RuntimeError("The HTTP service does not start.")
                await asyncio.sleep(0.01)
            print("ready", flush=True)
            await task
        finally:
            if control:
                control.close()
                await control.wait_closed()
            for number in list(self.active):
                await self.close(number)
            listener.close()
            if control:
                control_path.unlink(missing_ok=True)
            sessions.remove_by_pid(os.getpid())


if __name__ == "__main__":
    asyncio.run(Service(Config(**json.loads(sys.argv[1]))).run())
