from pathlib import Path

import pytest

from imd.config import load_config


def test_missing_config_uses_one_fixed_port(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    config = load_config()
    assert config.host == "0.0.0.0"
    assert config.port == 8000
    assert config.public_url == "http://0.0.0.0:8000"


def test_config_uses_user_home_and_executes_python(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    directory = tmp_path / ".imd"
    directory.mkdir()
    (directory / "config.py").write_text(
        'domain = "qubaitian.duckdns.org"\n'
        'config = {"host": "127.0.0.1", "port": 8123, '
        '"public_url": f"https://{domain}/"}\n'
    )
    monkeypatch.chdir(Path(__file__).parent)
    config = load_config()
    assert config.host == "127.0.0.1"
    assert config.port == 8123
    assert config.public_url == "https://qubaitian.duckdns.org"


@pytest.mark.parametrize(
    "source",
    [
        "config = None",
        "other = {}",
        'config = {"port": 0}',
        'config = {"port": True}',
        'config = {"port": 65536}',
        'config = {"ports": [8000]}',
        'config = {"public_url": "qubaitian.duckdns.org"}',
        'config = {"public_url": "https://example.com/path"}',
        'config = {"public_url": "https://user:secret@example.com"}',
        'config = {"public_url": "https://example.com/#token=secret"}',
    ],
)
def test_invalid_config_reports_its_path(tmp_path, monkeypatch, source):
    monkeypatch.setenv("HOME", str(tmp_path))
    directory = tmp_path / ".imd"
    directory.mkdir()
    (directory / "config.py").write_text(source)
    with pytest.raises(ValueError, match=r"config\.py"):
        load_config()
