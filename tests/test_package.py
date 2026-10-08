import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest


@pytest.fixture(scope="module")
def wheel(tmp_path_factory):
    directory = tmp_path_factory.mktemp("wheel")
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(directory)],
        cwd=Path(__file__).resolve().parent.parent, check=True, capture_output=True, text=True,
    )
    return next(directory.glob("*.whl"))


def test_wheel_contains_the_frontend(wheel):
    with ZipFile(wheel) as package:
        assert "imd/static/index.html" in package.namelist()
        assert any(name.startswith("imd/static/assets/") for name in package.namelist())


def test_installed_wheel_serves_the_editor_outside_the_repository(wheel, tmp_path):
    script = '''
import re
from pathlib import Path
from fastapi.testclient import TestClient
from imd.server import create_app

with TestClient(create_app(), base_url="http://localhost:8000") as client:
    response = client.get(str(Path.cwd()))
    assert response.status_code == 200, response.text
    assert "text/html" in response.headers["content-type"]
    assert (Path.cwd() / "imd.md").read_text() == ""
    assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', response.text)
    assert assets
    for asset in assets:
        assert client.get(asset).status_code == 200
    document = client.get("/api/document", params={"workspace": str(Path.cwd()), "path": "imd.md"})
    assert document.status_code == 200
'''
    result = subprocess.run(
        ["uv", "run", "--isolated", "--no-project", "--python", sys.executable,
         "--with", str(wheel), "--with", "httpx", "python", "-c", script],
        cwd=tmp_path, capture_output=True, text=True, check=False, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
