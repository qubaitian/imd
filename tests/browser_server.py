from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from fastapi import FastAPI

from imd.app import create_app


def main():
    with TemporaryDirectory(prefix="imd-browser-test-") as directory:
        root = Path(directory)
        children = [("", create_app("document.md", root, token="browser-test", markdown_commands=["printf"]))]
        panel_directory = root / "panels"
        panel_directory.mkdir()
        for name in ("a.md", "b.md", "c.md", "notes.txt"):
            (panel_directory / name).write_text(f"# {name}\n")
        children.append(
            (
                "/panels",
                create_app(
                    ["a.md", "b.md", "c.md"], panel_directory, token="browser-panels"
                ),
            )
        )
        for number in (1, 2):
            cwd = root / str(number)
            cwd.mkdir()
            children.append(
                (
                    f"/{number}",
                    create_app("document.md", cwd, token=f"browser-{number}"),
                )
            )

        @asynccontextmanager
        async def lifespan(app):
            async with AsyncExitStack() as stack:
                for _, child in children:
                    await stack.enter_async_context(
                        child.router.lifespan_context(child)
                    )
                yield

        app = FastAPI(lifespan=lifespan)
        for prefix, child in reversed(children):
            app.mount(prefix, child)
        uvicorn.run(app, host="127.0.0.1", port=18741, log_level="warning")


if __name__ == "__main__":
    main()
