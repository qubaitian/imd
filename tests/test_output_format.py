import pytest

from imd.output_format import MarkdownCommands


@pytest.mark.parametrize(
    "code, language, expected",
    [
        ("report show", "shell", True),
        ("report show today\n", "", True),
        ('report "show" "two words"', "shell", True),
        ("report show 'a; b | c'", "shell", True),
        ("report show # comment", "shell", True),
        ("report showcase", "shell", False),
        ("report", "shell", False),
        ("/usr/bin/report show", "shell", False),
        ("$CMD show", "shell", False),
        ("alias_name show", "shell", False),
        ("report show | head", "shell", False),
        ("report show; echo hello", "shell", False),
        ("report show\necho hello", "shell", False),
        ("report show && echo hello", "shell", False),
        ("report show &", "shell", False),
        ("if true; then report show; fi", "shell", False),
        ("for x in a; do report show; done", "shell", False),
        ("report() { echo hello; }", "shell", False),
        ("report show $(echo hello)", "shell", False),
        ('report show "$(echo hello)"', "shell", False),
        ("report show `echo hello`", "shell", False),
        ("report show > result.md", "shell", False),
        ("report show <<EOF\nhello\nEOF", "shell", False),
        ("report 'show", "shell", False),
        ("report show", "python", False),
        ("", "shell", False),
    ],
)
def test_matches_only_a_simple_command_prefix(code, language, expected):
    assert MarkdownCommands(["report show"]).matches(code, language) is expected


def test_matches_complete_arguments_without_expanding_them():
    commands = MarkdownCommands(['python3 "my report.py"', "/usr/bin/report"])
    assert commands.matches('python3 my\\ report.py today', "shell")
    assert commands.matches("/usr/bin/report today", "shell")
    assert not commands.matches("python3 my report.py", "shell")
    assert not commands.matches("python3 $SCRIPT", "shell")
    assert not commands.matches("report today", "shell")
    assert not MarkdownCommands([]).matches("report", "shell")


@pytest.mark.parametrize("entries", ["report", None, [1], [""], ["report | head"], ["'report"]])
def test_rejects_invalid_command_lists(entries):
    with pytest.raises(ValueError, match="markdown_commands"):
        MarkdownCommands(entries)
