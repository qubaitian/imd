import argparse
import sys

from . import session_api, sessions


def _port(value: str) -> int:
    try:
        return sessions.validate_port(int(value))
    except ValueError as error:
        raise argparse.ArgumentTypeError("Give a port from 1 through 65535.") from error


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Edit and run Markdown in the browser."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("open", help="Create a session in the current directory.")
    commands.add_parser("list", help="List all live sessions.")
    close = commands.add_parser("close", help="Close a session and keep its files.")
    close.add_argument("port", type=_port, help="The session port.")
    args = parser.parse_args()
    try:
        if args.command == "open":
            entries = [session_api.open_session()]
        elif args.command == "list":
            entries = session_api.list_sessions()
        else:
            session_api.close_session(args.port)
            return
        for entry in entries:
            print(sessions.format_entry(entry.url, entry.cwd, entry.paths), flush=True)
    except (ValueError, OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
