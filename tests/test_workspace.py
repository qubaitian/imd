import threading

import pytest

from imd.workspace import Conflict, Workspace


def test_lists_reads_and_saves_documents_with_a_revision(tmp_path):
    (tmp_path / "guide.md").write_text("# Guide\n")
    (tmp_path / "other.txt").write_text("hidden")
    workspace = Workspace(tmp_path)
    assert workspace.list() == ["guide.md"]
    document = workspace.read("guide.md")
    assert document["content"] == "# Guide\n"
    saved = workspace.save("guide.md", "# Changed\n", document["revision"])
    assert saved["content"] == "# Changed\n"
    with pytest.raises(Conflict):
        workspace.save("guide.md", "stale edit", document["revision"])
    assert (tmp_path / "guide.md").read_text() == "# Changed\n"


def test_rejects_paths_outside_the_workspace_and_non_markdown(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("outside")
    (root / "link.md").symlink_to(outside)
    workspace = Workspace(root)
    for path in ["../outside.md", str(outside), "link.md", "data.txt"]:
        with pytest.raises(ValueError):
            workspace.read(path)
    assert workspace.list() == []


def test_overlapping_saves_keep_one_writers_content(tmp_path, monkeypatch):
    file = tmp_path / "guide.md"
    file.write_text("base\n")
    workspace = Workspace(tmp_path)
    revision = workspace.read("guide.md")["revision"]
    original = Workspace._revision
    release = threading.Event()
    arrived = []

    def revision_with_pause(content):
        value = original(content)
        if content == "base\n":
            arrived.append(threading.current_thread().name)
            if len(arrived) >= 2:
                release.set()
            else:
                release.wait(0.5)
        return value

    monkeypatch.setattr(Workspace, "_revision", staticmethod(revision_with_pause))
    results = []

    def writer(content):
        try:
            saved = workspace.save("guide.md", content, revision)
        except Conflict:
            results.append(("conflict", content))
        else:
            results.append(("ok", saved["content"]))

    threads = [
        threading.Thread(target=writer, name="one", args=("FIRST-WRITER\n",)),
        threading.Thread(target=writer, name="two", args=("SECOND-WRITER\n",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    final = file.read_text()
    assert final in {"FIRST-WRITER\n", "SECOND-WRITER\n"}
    assert sorted(status for status, _ in results) == ["conflict", "ok"]
    assert ("ok", final) in results
    assert ("conflict", "FIRST-WRITER\n" if final == "SECOND-WRITER\n" else "SECOND-WRITER\n") in results
