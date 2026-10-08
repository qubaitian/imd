"""Document access within one local directory."""

import fcntl
import hashlib
import os
import tempfile
from pathlib import Path


class Conflict(Exception):
    """The saved document has changed since it was read."""


class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)

    def path(self, name: str) -> Path:
        relative = Path(name)
        if relative.is_absolute() or relative.suffix.lower() != ".md":
            raise ValueError("Use a relative Markdown path.")
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("The document must be inside the workspace.")
        return path

    def list(self) -> list[str]:
        documents = []
        for directory, folders, files in os.walk(self.root):
            folders[:] = [
                name
                for name in folders
                if not name.startswith(".") and name not in {"node_modules", "dist"}
            ]
            for name in files:
                relative = str((Path(directory) / name).relative_to(self.root))
                if name.lower().endswith(".md"):
                    try:
                        self.path(relative)
                    except ValueError:
                        continue
                    documents.append(relative)
        return sorted(documents)

    def open_default(self) -> dict:
        path = self.path("imd.md")
        try:
            with path.open("x", encoding="utf-8"):
                pass
        except FileExistsError:
            pass
        return self.read("imd.md")

    def read(self, name: str) -> dict:
        content = self.path(name).read_text(encoding="utf-8")
        return {"path": name, "content": content, "revision": self._revision(content)}

    def save(self, name: str, content: str, revision: str) -> dict:
        path = self.path(name)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            fcntl.flock(directory, fcntl.LOCK_EX)
            try:
                current = path.read_text(encoding="utf-8")
                if self._revision(current) != revision:
                    raise Conflict("The document changed on disk. Reopen it before saving.")
                descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".imd-")
                try:
                    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                        file.write(content)
                    os.chmod(temporary, path.stat().st_mode)
                    os.replace(temporary, path)
                finally:
                    Path(temporary).unlink(missing_ok=True)
                return {"path": name, "content": content, "revision": self._revision(content)}
            finally:
                fcntl.flock(directory, fcntl.LOCK_UN)
        finally:
            os.close(directory)

    @staticmethod
    def _revision(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
