import json
import subprocess
import sys
from pathlib import Path

import pytest

from imd import browser, paths


def test_directory_link_selects_the_session_path(tmp_path, monkeypatch):
    url = "https://example.com/2/#token=secret"
    monkeypatch.setattr(
        paths.sessions, "list_sessions", lambda: [{"cwd": str(tmp_path), "url": url}]
    )
    opened = []

    def open_url(url, *, match_path=False):
        opened.append((url, match_path))
        return {"action": "focused"}

    monkeypatch.setattr(browser, "open_url", open_url)
    assert paths.open_directory(tmp_path) == {"action": "focused"}
    assert opened == [(url, True)]


@pytest.mark.skipif(sys.platform != "darwin", reason="JXA requires macOS.")
def test_tab_matching_distinguishes_sessions_and_ignores_tokens():
    script = Path(browser.__file__).with_name("browser.js").read_text()
    script += """
function run() {
  return JSON.stringify([
    endpoint("https://example.com/1/#token=first", true) === endpoint("https://example.com/2/", true),
    endpoint("https://example.com/1/#token=first", true) === endpoint("https://example.com/1/", true),
    endpoint("https://example.com/1/", false) === endpoint("https://example.com/2/", false)
  ]);
}
"""
    result = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", script],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == [False, True, True]
