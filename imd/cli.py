import argparse

from . import session_api, sessions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Edit and run Markdown in the browser."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("open", help="Create a session in the current directory.")
    commands.add_parser("list", help="List all live sessions.")
    close = commands.add_parser("close", help="Close sessions and keep their files.")
    close.add_argument(
        "number",
        type=int,
        nargs="?",
        help="The session number from its URL path. Omit to close all sessions.",
    )
    args = parser.parse_args()
    try:
        if args.command == "open":
            entries = [session_api.open_session()]
        elif args.command == "list":
            entries = session_api.list_sessions()
        else:
            session_api.close_session(args.number)
            return
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f"imd: {exc}\n")
    for entry in entries:
        print(sessions.format_entry(entry.url, entry.cwd, entry.paths), flush=True)


if __name__ == "__main__":
    main()
