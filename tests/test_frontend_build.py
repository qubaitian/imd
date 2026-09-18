from pathlib import Path

import pytest

from hatch_build import build_frontend


def test_editable_install_does_not_run_npm(tmp_path):
    (tmp_path / "web").mkdir()

    def run(*args, **kwargs):
        raise AssertionError("Editable installs do not run npm.")

    build_frontend(tmp_path, "editable", "npm", run=run)


def test_missing_npm_fails_with_node_requirement(tmp_path):
    (tmp_path / "web").mkdir()
    with pytest.raises(RuntimeError, match="Node.js 22.12"):
        build_frontend(tmp_path, "standard", None, run=lambda *a, **k: None)


def test_wheel_build_runs_npm_ci_then_build(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    calls = []

    def run(args, cwd=None, check=False):
        calls.append((list(args), Path(cwd), check))
        index = tmp_path / "imd" / "static" / "index.html"
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text("ok", encoding="utf-8")

    build_frontend(tmp_path, "standard", "/usr/bin/npm", run=run)
    assert calls == [
        (["/usr/bin/npm", "ci"], web, True),
        (["/usr/bin/npm", "run", "build"], web, True),
    ]


def test_wheel_build_rebuilds_when_static_exists(tmp_path):
    (tmp_path / "web").mkdir()
    index = tmp_path / "imd" / "static" / "index.html"
    index.parent.mkdir(parents=True)
    index.write_text("old", encoding="utf-8")
    calls = []

    def run(args, cwd=None, check=False):
        calls.append(list(args))
        index.write_text("new", encoding="utf-8")

    build_frontend(tmp_path, "standard", "npm", run=run)
    assert len(calls) == 2
    assert calls[0] == ["npm", "ci"]
    assert calls[1] == ["npm", "run", "build"]


def test_wheel_build_fails_when_index_is_missing(tmp_path):
    (tmp_path / "web").mkdir()

    def run(*args, **kwargs):
        return None

    with pytest.raises(RuntimeError, match="imd/static/index.html"):
        build_frontend(tmp_path, "standard", "npm", run=run)
