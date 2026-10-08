import pytest

from imd.outputs import output_block, replace_output
from imd.terminal import TerminalCapture

SOURCE = "# Note\n\n```xonsh\nprint('hello')\n```\n\n<!-- 3f9a1c -->\n```txt\nold\n```\n\nKeep this paragraph.\n"


def test_replaces_only_the_marked_output_and_keeps_the_marker():
    updated = replace_output(SOURCE, "3f9a1c", "hello\n", "print('hello')\n")
    assert "old\n" not in updated
    assert "```txt\nhello\n```" in updated
    assert updated.count("<!-- 3f9a1c -->") == 1
    assert updated.endswith("Keep this paragraph.\n")
    assert output_block(updated, "3f9a1c")["code"] == "print('hello')\n"


def test_output_containing_fences_is_kept_inside_one_output_block():
    updated = replace_output(SOURCE, "3f9a1c", "```\n<script>example</script>\n")
    assert "````txt\n```\n<script>example</script>\n````" in updated
    assert output_block(updated, "3f9a1c")["output"] == "```\n<script>example</script>\n"


def test_updates_output_inside_a_blockquote():
    source = "> ```py\n> print(42)\n> ```\n> <!-- abc123 -->\n> ```txt\n> old\n> ```\n"
    updated = replace_output(source, "abc123", "42\n")
    assert "> ```txt\n> 42\n> ```" in updated
    assert output_block(updated, "abc123")["code"] == "print(42)\n"


def test_output_block_includes_the_code_language():
    source = SOURCE.replace("```xonsh", "```SH extra")
    assert output_block(source, "3f9a1c")["language"] == "sh"


def test_output_save_rejects_a_changed_language():
    with pytest.raises(ValueError, match="language changed"):
        replace_output(SOURCE, "3f9a1c", "reply", "print('hello')\n", "sh")


def test_rejects_ambiguous_markers_and_changed_or_removed_code():
    for source in [
        SOURCE + SOURCE,
        SOURCE.replace("print('hello')", "print('changed')"),
        "# Removed\n",
    ]:
        with pytest.raises(ValueError):
            replace_output(source, "3f9a1c", "hello", "print('hello')\n")


def test_terminal_capture_applies_carriage_returns_and_discards_control_sequences():
    capture = TerminalCapture(80, 24)
    capture.write("\x1b[32mfirst\x1b[0m\rfinal\r\nnext\r\n")
    assert capture.text() == "final\nnext\n"


def test_terminal_capture_restores_normal_screen_after_vim():
    capture = TerminalCapture(80, 24)
    capture.write("before\r\n\x1b[?1049h\x1b[2J\x1b[Hvim buffer\x1b[?1049lafter\r\n")
    assert capture.text() == "before\nafter\n"


def test_terminal_capture_ignores_private_sgr_sequences_from_vim():
    capture = TerminalCapture(80, 24)
    capture.write("before\r\n\x1b[?0m\x1b[?4;2mafter\r\n")
    assert capture.text() == "before\nafter\n"


@pytest.mark.parametrize("label", ["", "js extra", "txt", "custom"])
def test_any_code_fence_can_have_saved_output(label):
    source = SOURCE.replace("```xonsh", "```" + label)
    updated = replace_output(source, "3f9a1c", "reply\n")
    block = output_block(updated, "3f9a1c")
    assert block["language"] == (label.split() or ["xonsh"])[0]
    assert block["output"] == "reply\n"


def test_saved_output_cannot_be_the_code_for_another_run():
    source = SOURCE + "<!-- abc123 -->\n```txt\nsecond output\n```\n"
    with pytest.raises(ValueError, match="executable code"):
        output_block(source, "abc123")
