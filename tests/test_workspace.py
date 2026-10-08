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
