"""The xonsh process for one document."""

import fcntl
import json
import os
import signal
import socket
import subprocess
import sys
import termios
import traceback

from imd.agents import AgentCommands, AgentError


def main():
    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    control = socket.socket(fileno=int(sys.argv[1])).makefile("rw", encoding="utf-8")

    import xonsh.tools as xonsh_tools
    from xonsh.built_ins import XSH
    from xonsh.main import setup
    from xonsh.tools import XonshError

    setup(
        shell_type="none",
        history_backend="dummy",
        env={"XONSH_SUBPROC_CMD_RAISE_ERROR": True, "XONSH_INTERACTIVE": False},
    )
    XSH.env["PWD"] = os.getcwd()
    agent = AgentCommands()
    command_error = {"printed": False}
    original_print_exception = xonsh_tools.print_exception

    def report_command_error(msg=None, exc_info=None, source_msg=None):
        if exc_info is None:
            exc_info = sys.exc_info()
        error_type, error, _ = exc_info
        if error_type is not None and issubclass(error_type, (XonshError, subprocess.CalledProcessError)):
            command_error["printed"] = True
            text = str(error).strip()
            if text:
                print(text, file=sys.stderr, flush=True)
            return
        original_print_exception(msg, exc_info, source_msg)

    xonsh_tools.print_exception = report_command_error

    def send(message):
        control.write(json.dumps(message) + "\n")
        control.flush()

    # An interrupt outside user code would end the worker and its session.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    send({"type": "ready", "cwd": os.getcwd()})
    while True:
        line = control.readline()
        if not line:
            break
        message = json.loads(line)
        status = "ok"
        command_error["printed"] = False
        try:
            try:
                signal.signal(signal.SIGINT, signal.default_int_handler)
                if not agent.execute(
                    message["code"], message.get("language", "xonsh"), XSH.subproc_uncaptured
                ):
                    XSH.execer.exec(
                        message["code"] + "\n", glbs=XSH.ctx, locs=XSH.ctx, filename="<imd>"
                    )
            finally:
                signal.signal(signal.SIGINT, signal.SIG_IGN)
        except KeyboardInterrupt:
            status = "interrupted"
            print("\nRun interrupted.", flush=True)
        except AgentError as error:
            status = "error"
            print(error, flush=True)
        except subprocess.CalledProcessError as error:
            status = "error"
            if not command_error["printed"]:
                print(f"Command exited with status {error.returncode}.", flush=True)
        except XonshError as error:
            status = "error"
            if not command_error["printed"]:
                print(str(error).strip() or "Command failed.", flush=True)
        # User code can raise any exception.
        except (Exception, SystemExit):  # noqa: BLE001
            status = "error"
            traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        send({"type": "done", "id": message["id"], "status": status, "cwd": os.getcwd()})


if __name__ == "__main__":
    main()
