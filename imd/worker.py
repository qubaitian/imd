"""The xonsh process for one document."""

import fcntl
import json
import os
import socket
import sys
import termios
import traceback

from imd.agents import AgentCommands


def main():
    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    control = socket.socket(fileno=int(sys.argv[1])).makefile("rw", encoding="utf-8")

    from xonsh.built_ins import XSH
    from xonsh.main import setup

    setup(
        shell_type="none",
        history_backend="dummy",
        env={"XONSH_SUBPROC_CMD_RAISE_ERROR": True, "XONSH_INTERACTIVE": False},
    )
    XSH.env["PWD"] = os.getcwd()
    agent = AgentCommands()

    def send(message):
        control.write(json.dumps(message) + "\n")
        control.flush()

    send({"type": "ready", "cwd": os.getcwd()})
    while True:
        try:
            line = control.readline()
        except KeyboardInterrupt:
            continue
        if not line:
            break
        message = json.loads(line)
        status = "ok"
        try:
            if not agent.execute(
                message["code"], message.get("language", "xonsh"), XSH.subproc_uncaptured
            ):
                XSH.execer.exec(message["code"] + "\n", glbs=XSH.ctx, locs=XSH.ctx, filename="<imd>")
        except KeyboardInterrupt:
            status = "interrupted"
            print("\nRun interrupted.", flush=True)
        # User code can raise any exception.
        except (Exception, SystemExit):  # noqa: BLE001
            status = "error"
            traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        send({"type": "done", "id": message["id"], "status": status, "cwd": os.getcwd()})


if __name__ == "__main__":
    main()
