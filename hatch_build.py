"""Build frontend files into the wheel."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

try:
    from hatchling.builders.hooks.plugin.interface import BuildHookInterface
except ImportError:  # pragma: no cover
    BuildHookInterface = object


def build_frontend(root: Path, version: str, npm: str | None, run=subprocess.run) -> None:
    """Install Node packages and write `imd/static` for a wheel build."""
    if version == "editable":
        return
    if not npm:
        raise RuntimeError(
            "The frontend build needs Node.js 22.12 or later. "
            "Install Node.js, then run uv tool install . again."
        )
    web = root / "web"
    run([npm, "ci"], cwd=web, check=True)
    run([npm, "run", "build"], cwd=web, check=True)
    if not (root / "imd" / "static" / "index.html").is_file():
        raise RuntimeError("The frontend build did not write imd/static/index.html.")


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        build_frontend(Path(self.root), version, shutil.which("npm"))
