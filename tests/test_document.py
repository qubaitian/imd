import re

import pytest

from imd.document import blocks, with_output


def region(body, identity="outer"):
    return (
        f"<!-- imd:output:begin {identity} -->\n\n"
        f"{body}\n\n<!-- imd:output:end {identity} -->\n"
    )


def test_output_contains_markdown_and_runnable_code():
    source = "```python\nprint('result')\n```\n"
    result = with_output(source, 0, "# Result\n\n```python\n2 + 2\n```\n")
    items = blocks(result)
    assert [item["kind"] for item in items] == ["code", "output", "markdown", "code"]
    assert [item["parent"] for item in items] == [None, None, 1, 1]
    assert items[2]["raw"] == "# Result\n"
    assert items[3]["code"] == "2 + 2\n"
    identity = re.search(r"<!-- imd:output:begin (\w+) -->", result)[1]
    assert f"<!-- imd:output:end {identity} -->" in result


def test_nested_execution_and_parent_replacement():
    source = (
        "```python\n1\n```\n\n"
        + region("# Outer\n\n```python\n2\n```")
        + "\nKeep this.\n"
    )
    result = with_output(source, 3, "## Inner\n\n```python\n3\n```")
    items = blocks(result)
    assert [item["kind"] for item in items] == [
        "code",
        "output",
        "markdown",
        "code",
        "output",
        "markdown",
        "code",
        "markdown",
    ]
    assert [item["parent"] for item in items] == [None, None, 1, 1, 1, 4, 4, None]
    assert items[4]["end"] < items[1]["end"]
    result = with_output(result, 3, "Replacement")
    assert "# Outer" in result
    assert "## Inner" not in result
    assert "3\n```" not in result
    assert result.endswith("\nKeep this.\n")
    result = with_output(result, 0, "Final")
    assert "# Outer" not in result
    assert "Replacement" not in result
    assert [item["kind"] for item in blocks(result)] == [
        "code",
        "output",
        "markdown",
        "markdown",
    ]


def test_old_out_fences_are_ordinary_code():
    source = "```python\n1\n```\n\n```out\n2\n```\n"
    assert [item["kind"] for item in blocks(source)] == ["code", "code"]
    assert source.split("\n\n")[1] in with_output(source, 0, "New")
    assert "<!-- imd:output:begin" in with_output(source, 1, "New")


def test_markers_in_code_are_literal():
    source = "```markdown\n" + region("Example") + "```\n"
    assert [item["kind"] for item in blocks(source)] == ["code"]


@pytest.mark.parametrize(
    "source",
    [
        "<!-- imd:output:begin lost -->\n\nText\n",
        "<!-- imd:output:end lost -->\n",
        "<!-- imd:output:begin a -->\n\nText\n\n<!-- imd:output:end b -->\n",
    ],
)
def test_unpaired_markers_are_not_output(source):
    assert all(item["kind"] != "output" for item in blocks(source))


def test_unicode_offsets_and_crlf_in_nested_output():
    source = "😀\r\n\r\n" + region("```python\n2\n```").replace("\n", "\r\n")
    result = with_output(source, 2, "# 中文😀")
    assert "\n" not in result.replace("\r\n", "")
    for item in blocks(result):
        assert result[item["start"] : item["end"]] == item["raw"]
        assert (
            len(result[: item["start"]].encode("utf-16-le")) // 2 == item["start_utf16"]
        )
        assert len(result[: item["end"]].encode("utf-16-le")) // 2 == item["end_utf16"]


def test_empty_output_has_a_deletable_region():
    result = with_output("```python\npass\n```", 0, "")
    assert [item["kind"] for item in blocks(result)] == ["code", "output"]


def test_nonadjacent_output_stays_unchanged():
    suffix = "\nOther text.\n\n" + region("Keep")
    source = "```python\n1\n```\n" + suffix
    assert with_output(source, 0, "New").endswith(suffix)


def test_output_bounds_unclosed_markdown():
    source = "```python\n1\n```\n\nKeep this.\n"
    for output in ["```python\n2", "<!-- incomplete comment", "<div>\ntext"]:
        result = with_output(source, 0, output)
        items = blocks(result)
        assert items[1]["kind"] == "output"
        assert items[2]["parent"] == 1
        assert items[-1]["raw"] == "Keep this.\n"
        assert items[-1]["parent"] is None


def test_output_ids_do_not_collide_with_existing_markers(monkeypatch):
    from types import SimpleNamespace

    from imd import document

    identities = iter(["taken", "printed", "fresh"])
    monkeypatch.setattr(
        document, "uuid4", lambda: SimpleNamespace(hex=next(identities))
    )
    source = "```python\n1\n```\n\n" + region("Old", "taken")
    result = with_output(source, 0, region("New", "printed"))
    assert [item["id"] for item in blocks(result) if item["kind"] == "output"] == [
        "fresh",
        "printed",
    ]


def test_execution_closes_an_unclosed_fence_inside_output():
    source = region("```python\nprint('done')") + "\nKeep this.\n"
    result = with_output(source, 1, "**Done**")
    items = blocks(result)
    assert [item["kind"] for item in items] == [
        "output",
        "code",
        "output",
        "markdown",
        "markdown",
    ]
    assert [item["parent"] for item in items] == [None, 0, 0, 2, None]
    assert items[1]["code"].strip() == "print('done')"


def test_child_output_cannot_close_the_parent_output():
    source = region("```python\nprint('marker')\n```") + "\nKeep this.\n"
    result = with_output(source, 1, "<!-- imd:output:end outer -->")
    items = blocks(result)
    assert [item["kind"] for item in items] == [
        "output",
        "code",
        "output",
        "markdown",
        "markdown",
    ]
    assert [item["parent"] for item in items] == [None, 0, 0, 2, None]
    assert items[0]["raw"].endswith("<!-- imd:output:end outer -->\n")
    assert items[-1]["raw"] == "Keep this.\n"
