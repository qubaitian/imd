import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from imd import browser
from imd.app import create_app


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/test",
        "javascript:alert(1)",
        "http://",
        "http://host:99999",
        "https://host/\nnext",
    ],
)
def test_rejects_invalid_urls_without_automation(monkeypatch, url):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: pytest.fail("Automation runs.")
    )
    with pytest.raises(ValueError):
        browser.open_url(url)


def test_reports_automation_permission_failure(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "Not authorized (-1743)"),
    )
    with pytest.raises(RuntimeError, match="Automation"):
        browser.open_url("http://localhost:8000/a")


def test_passes_the_url_as_data_and_returns_the_browser_result(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    url = 'https://example.com/path?value="hello"&code=$(test)`test`#part'
    calls = []

    def run(args, **options):
        calls.append((args, options))
        return subprocess.CompletedProcess(args, 0, '{"action":"opened"}', "")

    monkeypatch.setattr(subprocess, "run", run)
    assert browser.open_url(url) == {"action": "opened"}
    args, options = calls[0]
    assert args[-1] == url
    assert args[:-1] == [
        "osascript",
        "-l",
        "JavaScript",
        str(Path(browser.__file__).with_name("browser.js")),
    ]
    assert not options.get("shell", False)


def test_reports_automation_timeout(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")

    def run(*args, **options):
        raise subprocess.TimeoutExpired(args, options["timeout"])

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(RuntimeError, match="does not respond"):
        browser.open_url("http://localhost:8000")


def test_reports_unsupported_platform_without_automation(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: pytest.fail("Automation runs.")
    )
    with pytest.raises(RuntimeError, match="macOS"):
        browser.open_url("http://localhost:8000")


def test_browser_endpoint_requires_token_and_reports_errors(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        browser, "open_url", lambda url: calls.append(url) or {"action": "focused"}
    )
    app = create_app("links.md", tmp_path, token="link-test")
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/browser/open", json={"url": "https://example.com"}
            ).status_code
            == 401
        )
        assert calls == []
        client.headers["Authorization"] = "Bearer link-test"
        response = client.post(
            "/api/browser/open", json={"url": "https://example.com/path"}
        )
        assert response.json() == {"action": "focused"}
        assert calls == ["https://example.com/path"]

        def fail(url):
            raise RuntimeError("Allow Chrome in Automation.")

        monkeypatch.setattr(browser, "open_url", fail)
        response = client.post("/api/browser/open", json={"url": "https://example.com"})
        assert response.status_code == 503
        assert "Automation" in response.json()["detail"]


@pytest.mark.skipif(sys.platform != "darwin", reason="JXA requires macOS.")
@pytest.mark.parametrize(
    "windows,url,expected",
    [
        (
            [
                ["http://localhost:8000/a", "http://localhost:8000/b"],
                ["http://localhost:8000/c"],
            ],
            "http://localhost:8000/new?x=1#token",
            [0, 0, "focused"],
        ),
        (
            [["https://example.com"], ["http://localhost:8000/a"]],
            "http://localhost:8000/b",
            [1, 0, "focused"],
        ),
        ([["http://EXAMPLE.com/a"]], "http://example.com:80/b", [0, 0, "focused"]),
        ([["https://example.com/a"]], "https://example.com:443/b", [0, 0, "focused"]),
        ([["http://[::1]:8000/a"]], "http://[::1]:8000/b", [0, 0, "focused"]),
        ([["http://127.0.0.1:8000/a"]], "http://localhost:8000/b", [0, 1, "opened"]),
        (
            [["https://localhost:8000/a", "http://localhost:8001/a"]],
            "http://localhost:8000/b",
            [0, 2, "opened"],
        ),
        ([["chrome://newtab/"]], "http://localhost:8000/b", [0, 1, "opened"]),
        ([], "http://localhost:8000/b", [0, 0, "opened"]),
    ],
)
def test_native_browser_script_preserves_tabs_and_selects_match(windows, url, expected):
    script = Path(browser.__file__).with_name("browser.js").read_text()
    harness = """
const initial = WINDOWS;
const selected = [];
let activated = false;
function windowStub(urls, index) {
    const tabs = urls.map(url => {
        const tab = {};
        Object.defineProperty(tab, 'url', {get: () => () => url, set: value => {url = value;}});
        return tab;
    });
    const win = {tabs: () => tabs};
    win.tabs.push = tab => tabs.push(tab);
    Object.defineProperty(win, 'activeTabIndex', {set: n => {selected[0] = index; selected[1] = n - 1;}});
    return win;
}
const windows = initial.map(windowStub);
const chrome = {
    windows: () => windows,
    Window: () => windowStub(['chrome://newtab/'], windows.length),
    Tab: props => ({url: () => props.url}),
    activate: () => {activated = true;}
};
chrome.windows.push = win => windows.unshift(win);
function Application() {return chrome;}
function run() {
    const result = openChrome(URL_VALUE);
    if (!activated) throw Error('Chrome does not activate.');
    if (result.action === 'opened' && windows[selected[0]].tabs()[selected[1]].url() !== URL_VALUE) throw Error('The new tab has the wrong URL.');
    for (let w = 0; w < initial.length; w++) {
        for (let t = 0; t < initial[w].length; t++) {
            if (windows[w].tabs()[t].url() !== initial[w][t]) throw Error('An existing URL changes.');
        }
    }
    return JSON.stringify([...selected, result.action]);
}
""".replace("WINDOWS", json.dumps(windows)).replace("URL_VALUE", json.dumps(url))
    combined = (
        "function scenario() {\n"
        + script
        + harness
        + "\nreturn run();\n}\nfunction run() {return scenario();}"
    )
    result = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", combined],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
