"""Run document code in one persistent shell on a PTY."""

import codecs
import fcntl
import os
import pty
import pwd
import re
import secrets
import select
import shlex
import shutil
import signal
import struct
import tempfile
import termios
from pathlib import Path
from threading import Lock
from time import monotonic, sleep

from .output import Output

COLUMNS = 100
ROWS = 24
START_TIMEOUT = 30
CLOSE_GRACE = 2
LANGUAGES = {"", "shell", "python"}
UNSUPPORTED = {"fish", "csh", "tcsh"}
LINE_EDITOR = {"zsh": "unsetopt zle", "bash": "set +o emacs; set +o vi"}
MARKER = re.compile(r"\x1b\]imd;([0-9a-f]+);([be]);([0-9]*)\x07")
MARKER_PREFIX = "\x1b]imd;"
LOST = "The shell stopped. The state is lost.\n"
HELPER = r"""__imd_marker() { printf '\033]imd;%s;%s;%s\007' "$1" "$2" "$3"; }
__imd_run() {
  __imd_id=$1
  __imd_mode=$2
  __imd_file=$3
  shift 3
  __imd_done=
  trap '__imd_marker "$__imd_id" e $?; __imd_done=1' INT
  __imd_marker "$__imd_id" b ''
  if [ "$__imd_mode" = python ]; then
    python3 "$__imd_file"
  else
    . "$__imd_file"
  fi
  __imd_status=$?
  [ -n "$__imd_done" ] || __imd_marker "$__imd_id" e "$__imd_status"
  trap - INT
}
"""


def check_language(language: str) -> str:
    """Accept a shell block or a python block and reject every other tag."""
    language = (language or "").strip().lower()
    if language not in LANGUAGES:
        raise ValueError(
            "IMD runs shell blocks and python blocks. "
            f"It does not run {language} blocks."
        )
    return language


def _shell_path() -> str:
    return os.environ.get("SHELL") or pwd.getpwuid(os.getuid()).pw_shell or "/bin/sh"


def _held(text: str) -> int:
    """Hold back the tail that can still grow into a marker."""
    index = text.rfind("\x1b")
    if index == -1:
        return 0
    tail = text[index:]
    if "\x07" in tail:
        return 0
    if tail.startswith(MARKER_PREFIX) or MARKER_PREFIX.startswith(tail):
        return len(tail)
    return 0


class Shell:
    """Run blocks in one interactive shell and return the terminal text."""

    def __init__(self, cwd: Path, session_token: str = ""):
        self.cwd = Path(cwd)
        self.session_token = session_token
        self.guard = Lock()
        self.directory = None
        self.master = None
        self.pid = None
        self.decoder = None
        self.pending = ""
        self.running = False

    def execute(self, code: str, language: str = "", emit=None) -> str:
        language = check_language(language)
        if self.master is None:
            self._start()
        return self._run(code, language, emit, None)

    def send(self, value: str) -> None:
        """Pass keys to the terminal without change."""
        with self.guard:
            if self.master is None:
                return
            data = value.encode("utf-8")
            try:
                while data:
                    data = data[os.write(self.master, data) :]
            except OSError:
                pass

    def interrupt(self) -> None:
        self.send("\x03")

    def kill(self) -> None:
        pid = self.pid
        if pid is None:
            return
        try:
            os.killpg(pid, signal.SIGKILL)
        except OSError:
            pass

    def close(self) -> None:
        """Interrupt the running command, then stop the shell and its files."""
        self.interrupt()
        deadline = monotonic() + CLOSE_GRACE
        while self.running and monotonic() < deadline:
            sleep(0.02)
        self.kill()
        self._release()
        if self.directory is not None:
            shutil.rmtree(self.directory, ignore_errors=True)
            self.directory = None

    def _start(self) -> None:
        path = _shell_path()
        name = Path(path).name
        if name in UNSUPPORTED:
            raise RuntimeError(
                f"IMD needs a POSIX shell. SHELL is {path}. "
                "Set SHELL to bash, zsh, or sh."
            )
        if self.directory is None:
            self.directory = Path(tempfile.mkdtemp(prefix="imd-"))
        helper = self.directory / "helper.sh"
        helper.write_text(HELPER, encoding="utf-8")
        pid, master = pty.fork()
        if pid == 0:
            self._child(path)
        self.pid = pid
        self.master = master
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.pending = ""
        fcntl.ioctl(
            master, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLUMNS, 0, 0)
        )
        try:
            if name in LINE_EDITOR:
                self.send(LINE_EDITOR[name] + "\n")
            self.send(f". {shlex.quote(str(helper))}\n")
            self._run("", "shell", None, START_TIMEOUT)
            if self.master is None:
                raise RuntimeError("The shell stops during start.")
        except BaseException:
            self.kill()
            self._release()
            raise

    def _child(self, path: str) -> None:
        try:
            os.chdir(self.cwd)
            os.environ.update(
                {
                    "TERM": "xterm-256color",
                    "COLUMNS": str(COLUMNS),
                    "LINES": str(ROWS),
                    "IMD_SESSION_TOKEN": self.session_token,
                }
            )
            os.execv(path, [path, "-i"])
        except BaseException:
            pass
        os._exit(1)

    def _run(self, code: str, language: str, emit, timeout) -> str:
        run_id = secrets.token_hex(8)
        mode = "python" if language == "python" else "shell"
        path = self.directory / f"{run_id}{'.py' if mode == 'python' else '.sh'}"
        text = code.replace("\r\n", "\n").replace("\r", "\n")
        path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        self.running = True
        try:
            self.send(f"__imd_run {run_id} {mode} {shlex.quote(str(path))}\n")
            return self._collect(run_id, emit, timeout)
        finally:
            self.running = False
            path.unlink(missing_ok=True)

    def _collect(self, run_id: str, emit, timeout) -> str:
        output = Output()
        started = False
        deadline = None if timeout is None else monotonic() + timeout

        def show(text):
            if text:
                output.feed(text)
                if emit:
                    emit(text)

        while True:
            data = self._read()
            if data is None:
                self._release()
                show(("" if output.column == 0 else "\n") + LOST)
                return output.text
            self.pending += data
            while (match := MARKER.search(self.pending)) is not None:
                if started:
                    show(self.pending[: match.start()])
                self.pending = self.pending[match.end() :]
                identity, kind, _ = match.groups()
                if identity != run_id:
                    continue
                if kind == "b":
                    started = True
                else:
                    return output.text
            keep = len(self.pending) - _held(self.pending)
            if started:
                show(self.pending[:keep])
            self.pending = self.pending[keep:]
            if deadline is not None and monotonic() > deadline:
                raise RuntimeError(
                    f"The shell does not answer within {timeout} seconds."
                )

    def _read(self) -> str | None:
        master = self.master
        if master is None:
            return None
        try:
            if not select.select([master], [], [], 0.05)[0]:
                return ""
            data = os.read(master, 65536)
        except OSError:
            data = b""
        return self.decoder.decode(data) if data else None

    def _release(self) -> None:
        with self.guard:
            pid, master = self.pid, self.master
            self.pid = self.master = None
        if master is not None:
            try:
                os.close(master)
            except OSError:
                pass
        if pid is not None:
            try:
                os.waitpid(pid, 0)
            except OSError:
                pass
