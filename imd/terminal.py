"""Run a shell command with a terminal and direct key input."""

import codecs
import fcntl
import json
import os
import pty
import select
import signal
import struct
import subprocess
import sys
import termios
import uuid


def run_shell(shell, command):
    if command.rstrip().endswith("&"):
        raise OSError("Background processes are not supported.")
    command = shell.var_expand(command, depth=2)
    kernel = shell.kernel
    parent = kernel.get_parent("shell")
    request_id = uuid.uuid4().hex
    master, slave = pty.openpty()
    process = None
    decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def publish(text):
        if text:
            kernel.session.send(
                kernel.iopub_socket,
                "imd_terminal_output",
                {"id": request_id, "text": text},
                parent,
            )

    try:
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
        process = subprocess.Popen(
            [sys.executable, "-m", "imd.terminal", command],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            start_new_session=True,
            env={**os.environ, "TERM": "xterm-256color", "COLUMNS": "100", "LINES": "24"},
        )
        os.close(slave)
        slave = None
        sys.stdout.flush()
        sys.stderr.flush()
        kernel.session.send(
            kernel.iopub_socket,
            "imd_terminal_start",
            {"id": request_id, "pid": process.pid},
            parent,
        )
        kernel.session.send(
            kernel.stdin_socket,
            "input_request",
            {"prompt": "", "password": False},
            parent,
            ident=kernel._parent_ident["shell"],
            metadata={"imd_terminal": request_id},
        )
        while True:
            readable, _, _ = select.select([master], [], [], 0.02)
            if readable:
                if process.poll() is not None:
                    break
                try:
                    data = os.read(master, 65536)
                except OSError:
                    break
                if not data:
                    break
                publish(decoder.decode(data))
            if kernel.stdin_socket.poll(0):
                _, reply = kernel.session.recv(kernel.stdin_socket)
                if reply is not None:
                    value = json.loads(reply["content"]["value"])
                    if isinstance(value, dict) and value.get("id") == request_id:
                        data = value["value"].encode("utf-8")
                        while data:
                            data = data[os.write(master, data) :]
            if not readable and process.poll() is not None:
                break
        publish(decoder.decode(b"", final=True))
        shell.user_ns["_exit_code"] = process.wait()
    finally:
        try:
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        finally:
            os.close(master)
            if slave is not None:
                os.close(slave)
            kernel.session.send(
                kernel.iopub_socket,
                "imd_terminal_end",
                {"id": request_id},
                parent,
            )


if __name__ == "__main__":
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    shell_path = os.environ.get("SHELL") or "/bin/sh"
    os.execv(shell_path, [shell_path, "-c", sys.argv[1]])
