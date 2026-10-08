"""Persistent document sessions with a console and serialized runs."""

import asyncio
import codecs
import contextlib
import fcntl
import json
import os
import pty
import signal
import socket
import struct
import sys
import termios
import uuid
from pathlib import Path

from imd.terminal import TerminalCapture


class Session:
    def __init__(self, cwd: Path):
        self.cwd = str(cwd)
        self.output = ""
        self.state = "starting"
        self._listeners: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Future] = {}
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._closed = False
        self._columns, self._rows = 80, 24
        self._capture = None
        self._current = None
        self._runs = {}

    @classmethod
    async def open(cls, cwd: Path):
        self = cls(cwd)
        self._loop = asyncio.get_running_loop()
        self._ready = self._loop.create_future()
        master, slave = pty.openpty()
        parent, child = socket.socketpair()
        self._master = master
        try:
            self._process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-u",
                "-c",
                "import sys; sys.path.insert(0, sys.argv.pop(1)); "
                "from imd.worker import main; main()",
                str(Path(__file__).resolve().parent.parent),
                str(child.fileno()),
                cwd=cwd,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                pass_fds=(child.fileno(),),
                env={**os.environ, "TERM": "xterm-256color"},
            )
        except BaseException:
            os.close(master)
            parent.close()
            raise
        finally:
            os.close(slave)
            child.close()
        os.set_blocking(master, False)
        self._reader, self._writer = await asyncio.open_connection(sock=parent)
        self._loop.add_reader(master, self._read_output)
        self._control_task = asyncio.create_task(self._read_control())
        try:
            await asyncio.wait_for(self._ready, 15)
        except BaseException:
            await self.close()
            raise
        return self

    def snapshot(self):
        return {
            "type": "snapshot",
            "output": self.output,
            "state": self.state,
            "cwd": self.cwd,
            "runs": list(self._runs.values()),
        }

    def subscribe(self):
        queue = asyncio.Queue(maxsize=1024)
        queue.put_nowait(self.snapshot())
        self._listeners.add(queue)
        return queue

    def unsubscribe(self, queue):
        self._listeners.discard(queue)

    def publish(self, event):
        if event["type"] == "save_error":
            run = self._runs.get(event.get("block_id"))
            if run and run["id"] == event.get("id"):
                run["saveError"] = event["message"]
        self._emit(event)

    def _emit(self, event):
        for queue in tuple(self._listeners):
            if queue.full():
                self._listeners.discard(queue)
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait({"type": "closed", "reason": "Console connection is too slow."})
            else:
                queue.put_nowait(event)

    def _read_output(self):
        while True:
            try:
                data = os.read(self._master, 65536)
            except BlockingIOError:
                return
            except OSError:
                self._loop.remove_reader(self._master)
                return
            if not data:
                self._loop.remove_reader(self._master)
                return
            text = self._decoder.decode(data)
            self.output = (self.output + text)[-1_000_000:]
            if self._current:
                self._current["output"] = (self._current["output"] + text)[-1_000_000:]
                self._capture.write(text)
            self._emit(
                {
                    "type": "output",
                    "data": text,
                    "id": self._current["id"] if self._current else None,
                    "block_id": self._current["block_id"] if self._current else None,
                }
            )

    async def _read_control(self):
        try:
            while line := await self._reader.readline():
                message = json.loads(line)
                self.cwd = message["cwd"]
                self._read_output()
                self.state = "ready"
                if message["type"] == "ready":
                    self._ready.set_result(None)
                elif future := self._pending.get(message["id"]):
                    message["block_id"] = self._current["block_id"]
                    message["text"] = self._capture.text()
                    self._current.update(message)
                    self._current = None
                    future.set_result(message)
                    self._emit(message)
        finally:
            self.state = "closed"
            error = RuntimeError("The session process ended. Reset the session to continue.")
            if not self._ready.done():
                self._ready.set_exception(error)
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(error)
            self._emit({"type": "closed", "reason": str(error)})

    async def run(
        self, code: str, run_id: str | None = None, block_id: str | None = None,
        *, language: str = "xonsh",
    ):
        run_id = run_id or uuid.uuid4().hex
        self._emit({"type": "queued", "id": run_id, "block_id": block_id})
        async with self._lock:
            if self._closed or self.state == "closed":
                raise RuntimeError("The session is closed.")
            future = self._loop.create_future()
            self._pending[run_id] = future
            self._capture = TerminalCapture(self._columns, self._rows)
            self._current = {"id": run_id, "block_id": block_id, "output": "", "status": "running"}
            self._runs[block_id or run_id] = self._current
            while len(self._runs) > 100:
                self._runs.pop(next(iter(self._runs)))
            self.state = "running"
            self._emit({"type": "running", "id": run_id, "block_id": block_id, "cwd": self.cwd})
            self._writer.write(
                (json.dumps({"id": run_id, "code": code, "language": language}) + "\n").encode()
            )
            try:
                await self._writer.drain()
                return await asyncio.shield(future)
            finally:
                self._pending.pop(run_id, None)

    def write(self, data: str):
        if not self._closed and self.state == "running":
            os.write(self._master, data.encode())

    def resize(self, columns: int, rows: int):
        if not self._closed:
            self._columns, self._rows = columns, rows
            if self._capture:
                self._capture.resize(columns, rows)
            fcntl.ioctl(self._master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))

    def interrupt(self):
        if not self._closed and self.state == "running":
            foreground = os.tcgetpgrp(self._master)
            with contextlib.suppress(ProcessLookupError):
                if foreground > 0:
                    os.killpg(foreground, signal.SIGINT)

    async def close(self):
        if self._closed:
            return
        self._closed = True
        self._emit({"type": "closed", "reason": "The session was reset or stopped."})
        self._loop.remove_reader(self._master)
        # End a foreground command before ending its xonsh process.
        with contextlib.suppress(ProcessLookupError, OSError):
            foreground = os.tcgetpgrp(self._master)
            if foreground > 0 and foreground != self._process.pid:
                os.killpg(foreground, signal.SIGKILL)
            os.killpg(self._process.pid, signal.SIGKILL)
        await self._process.wait()
        self._writer.close()
        with contextlib.suppress(ConnectionError):
            await self._writer.wait_closed()
        await self._control_task
        os.close(self._master)


class Sessions:
    def __init__(self):
        self._sessions: dict[Path, Session] = {}
        self._lock = asyncio.Lock()

    async def get(self, document: Path) -> Session:
        document = document.resolve()
        async with self._lock:
            if document not in self._sessions:
                self._sessions[document] = await Session.open(document.parent)
            return self._sessions[document]

    async def reset(self, document: Path) -> Session:
        document = document.resolve()
        async with self._lock:
            if previous := self._sessions.pop(document, None):
                await previous.close()
            self._sessions[document] = await Session.open(document.parent)
            return self._sessions[document]

    async def close(self):
        async with self._lock:
            await asyncio.gather(*(session.close() for session in self._sessions.values()))
            self._sessions.clear()
