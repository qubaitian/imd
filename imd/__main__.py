"""Start the local IMD service."""

import argparse
from pathlib import Path

import uvicorn

from imd.server import create_app


def main():
    parser = argparse.ArgumentParser(
        description="Open Markdown files with persistent xonsh sessions."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Workspace directory")
    parser.add_argument("--port", type=int, default=8000, help="Local service port")
    args = parser.parse_args()
    uvicorn.run(create_app(args.root), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
