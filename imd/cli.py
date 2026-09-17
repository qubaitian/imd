import argparse

from . import session_api, sessions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Edit and run Markdown in the browser."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("open", help="Create a session in the current directory.")
    commands.add_parser("list", help="List all live sessions.")
    close = commands.add_parser("close", help="Close a session and keep its files.")
    close.add_argument("port", help="The session port.")
    args = parser.parse_args()
    if args.command == "open":
        entries = [session_api.open_session()]
    elif args.command == "list":
        entries = session_api.list_sessions()
    else:
        session_api.close_session(sessions.validate_port(int(args.port)))
        return
    for entry in entries:
        print(sessions.format_entry(entry.url, entry.cwd, entry.paths), flush=True)


if __name__ == "__main__":
    main()
