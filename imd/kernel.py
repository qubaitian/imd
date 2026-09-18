import json
import os
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock
from time import monotonic, sleep

from jupyter_client import KernelManager

from .output import Output


class Kernel:
    def __init__(self, cwd: Path, session_token: str = ""):
        self.cwd = cwd
        self.session_token = session_token
        self.manager = None
        self.client = None
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="imd-kernel")
        self.inputs = Queue()
        self.guard = Lock()
        self.operation = Lock()
        self.request = None
        self.terminal_pgid = None
        self.stopping = Event()

    def execute(self, code: str, emit=None) -> str:
        with self.operation:
            return self.worker.submit(self._run, code, emit).result()

    def complete(self, code: str, cursor: int) -> dict:
        if not 0 <= cursor <= len(code):
            raise ValueError("The cursor must be inside the code.")
        empty = {"matches": [], "cursor_start": cursor, "cursor_end": cursor}
        if not self.operation.acquire(blocking=False):
            return empty
        try:
            return self.worker.submit(self._complete, code, cursor, empty).result()
        finally:
            self.operation.release()

    def _complete(self, code, cursor, empty):
        if self.manager is None:
            self._start()
        while self.client.iopub_channel.msg_ready():
            self.client.get_iopub_msg(timeout=0)
        message_id = self.client.complete(code, cursor_pos=cursor)
        deadline = monotonic() + 2
        while (remaining := deadline - monotonic()) > 0:
            if not self.client.shell_channel.msg_ready():
                sleep(min(0.02, remaining))
                continue
            message = self.client.get_shell_msg(timeout=remaining)
            if message["parent_header"].get("msg_id") != message_id:
                continue
            content = message["content"]
            if content.get("status") != "ok":
                return empty
            return {key: content[key] for key in empty}
        return empty

    def input(self, request_id: str, value: str):
        with self.guard:
            if self.request is None or self.request["id"] != request_id:
                raise ValueError("This input request is no longer active.")
            request = self.request
            if not request["terminal"]:
                self.request = None
            self.inputs.put((request, value))

    def interrupt(self):
        self.stopping.set()
        if self._kill_terminal():
            return
        if self.manager is not None and self.manager.has_kernel:
            self.manager.interrupt_kernel()

    def _kill_terminal(self):
        with self.guard:
            pgid = self.terminal_pgid
            self.terminal_pgid = None
        if pgid is None or pgid <= 1:
            return False
        try:
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            return False
        return True

    def _start(self):
        manager = KernelManager(kernel_name="python3")
        manager.kernel_spec.argv = [
            sys.executable,
            "-m",
            "ipykernel_launcher",
            "-f",
            "{connection_file}",
        ]
        self.manager = manager
        manager.start_kernel(
            cwd=str(self.cwd),
            env={**os.environ, "IMD_SESSION_TOKEN": self.session_token},
            extra_arguments=[
                "--InteractiveShell.automagic=True",
                "--InteractiveShell.colors=NoColor",
            ],
        )
        self.client = manager.blocking_client()
        self.client.start_channels()
        self.client.wait_for_ready(timeout=30)
        self._execute(
            "%load_ext imd.ipython_extension", lambda event: None, starting=True
        )

    def _run(self, code, emit):
        try:
            if self.manager is None:
                self._start()
            if self.stopping.is_set():
                output = "KeyboardInterrupt\n"
                if emit:
                    emit({"type": "output", "text": output})
                return output
            return self._execute(code, emit or (lambda event: None))
        finally:
            with self.guard:
                self.request = None
                self.terminal_pgid = None
            self.stopping.clear()
            while not self.inputs.empty():
                self.inputs.get()

    def _execute(self, code, emit, starting=False):
        message_id = self.client.execute(
            code, store_history=True, allow_stdin=True, stop_on_error=True
        )
        output = Output()
        clear_on_next = False
        closed_terminals = set()
        halt = None
        while True:
            if self.stopping.is_set() and not starting:
                self._kill_terminal()
                if halt is None:
                    halt = monotonic()
                elif monotonic() - halt > 2:
                    break
            if not self.inputs.empty():
                request, value = self.inputs.get()
                if request["terminal"]:
                    self.client.input(json.dumps({"id": request["id"], "value": value}))
                else:
                    self.client.input(value)
                    output.feed(("" if request["password"] else value) + "\n")
                    emit({"type": "output", "text": output.text})
                    emit({"type": "input", "id": None})
            if (
                not self.client.iopub_channel.msg_ready()
                and self.client.stdin_channel.msg_ready()
            ):
                message = self.client.get_stdin_msg(timeout=0)
                if message["parent_header"].get("msg_id") == message_id:
                    content = message["content"]
                    terminal = message.get("metadata", {}).get("imd_terminal")
                    if terminal not in closed_terminals:
                        request = {
                            "type": "input",
                            "id": terminal or message["header"]["msg_id"],
                            "terminal": bool(terminal),
                            "prompt": content["prompt"],
                            "password": content.get("password", False),
                        }
                        with self.guard:
                            self.request = request
                        if not terminal:
                            if clear_on_next:
                                output.clear()
                                clear_on_next = False
                            output.feed(request["prompt"])
                            emit({"type": "output", "text": output.text})
                        emit(request)
            if not self.client.iopub_channel.msg_ready():
                if not self.manager.is_alive():
                    raise RuntimeError("The IPython session stopped. Start imd again.")
                sleep(0.02)
                continue
            message = self.client.get_iopub_msg(timeout=0.02)
            if message["parent_header"].get("msg_id") != message_id:
                continue
            kind, content = message["msg_type"], message["content"]
            if kind == "status":
                if content["execution_state"] == "idle":
                    break
            if kind == "imd_terminal_start":
                with self.guard:
                    self.terminal_pgid = content["pid"]
                if self.stopping.is_set() and not starting:
                    self._kill_terminal()
            elif kind == "imd_terminal_end":
                closed_terminals.add(content["id"])
                with self.guard:
                    self.terminal_pgid = None
                    if self.request and self.request["id"] == content["id"]:
                        self.request = None
                        emit({"type": "input", "id": None})
            elif kind == "clear_output":
                if content.get("wait"):
                    clear_on_next = True
                else:
                    output.clear()
                    emit({"type": "output", "text": output.text})
            elif kind in {
                "stream",
                "execute_result",
                "display_data",
                "error",
                "imd_terminal_output",
            }:
                if kind == "imd_terminal_output" and self.stopping.is_set():
                    continue
                reset = clear_on_next
                if clear_on_next:
                    output.clear()
                    clear_on_next = False
                if kind in {"stream", "imd_terminal_output"}:
                    output.feed(content["text"])
                elif kind == "error":
                    output.feed("\n".join(content["traceback"]) + "\n")
                else:
                    text = content.get("data", {}).get("text/plain", "")
                    if text:
                        output.feed(text + ("" if text.endswith("\n") else "\n"))
                event = {"type": "output", "text": output.text}
                if kind == "imd_terminal_output":
                    event.update(
                        terminal=content["id"], data=content["text"], reset=reset
                    )
                emit(event)
        while True:
            try:
                reply = self.client.get_shell_msg(
                    timeout=2 if self.stopping.is_set() else 5
                )
            except Empty:
                if self.stopping.is_set():
                    break
                raise
            if reply["parent_header"].get("msg_id") == message_id:
                break
        return output.text

    def _close(self):
        if self.client:
            self.client.stop_channels()
        if self.manager and self.manager.has_kernel:
            self.manager.shutdown_kernel(now=True)

    def close(self):
        self.interrupt()
        with self.operation:
            self.worker.submit(self._close).result()
            self.worker.shutdown()
