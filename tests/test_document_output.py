import pytest

from imd.document import blocks, with_output


SOURCE = "```shell\nreport show\n```\n"


@pytest.mark.parametrize("text", ["# Log\n  aligned  text\n", "```python\nprint(1)\n```\n", "````\n~~~\n", "<script>hello</script>\n"])
def test_plain_output_round_trips_as_one_non_executable_fence(text):
    result = with_output(SOURCE, 0, text)
    items = blocks(result)
    assert [item["kind"] for item in items] == ["code", "output", "text"]
    assert items[-1]["language"] == "output"
    assert items[-1]["code"] == text
    assert items[-1]["parent"] == 1
    with pytest.raises(ValueError, match="code block"):
        with_output(result, 2, "no")


def test_markdown_output_keeps_nested_code_and_replaces_the_whole_region():
    result = with_output(SOURCE, 0, "# Report\n\n```python\nprint(1)\n```\n", markdown=True)
    assert [item["kind"] for item in blocks(result)] == ["code", "output", "markdown", "code"]
    nested = with_output(result, 3, "1\n")
    assert blocks(nested)[-1]["kind"] == "text"
    replaced = with_output(nested, 0, "plain\n")
    assert [item["kind"] for item in blocks(replaced)] == ["code", "output", "text"]
    assert "# Report" not in replaced
    assert blocks(replaced)[-1]["code"] == "plain\n"


def test_output_fences_are_non_executable_outside_output_regions_too():
    assert blocks("```output\nhello\n```\n")[0]["kind"] == "text"
    assert blocks("```out\nhello\n```\n")[0]["kind"] == "code"


def test_empty_output_and_crlf_keep_document_structure():
    assert [item["kind"] for item in blocks(with_output(SOURCE, 0, ""))] == ["code", "output"]
    result = with_output(SOURCE.replace("\n", "\r\n"), 0, "hello\nworld")
    assert "\n" not in result.replace("\r\n", "")
    assert blocks(result)[-1]["code"] == "hello\nworld\n"


def test_output_marker_text_stays_inside_the_plain_fence():
    text = "<!-- imd:output:begin fake -->\n```python\nprint(1)\n```\n<!-- imd:output:end fake -->\n"
    result = with_output(SOURCE, 0, text)
    assert len(blocks(result)) == 3
    assert blocks(result)[-1]["code"] == text
