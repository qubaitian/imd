from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn

from imd.app import create_app


def main():
    with TemporaryDirectory(prefix="imd-browser-test-") as directory:
        app = create_app("document.md", Path(directory), token="browser-test")
        uvicorn.run(app, host="127.0.0.1", port=18741, log_level="warning")


if __name__ == "__main__":
    main()
