import os
from pathlib import Path
from threading import Thread, Timer
from time import sleep

import pytest

from imd.shell import Shell, check_language


@pytest.fixture
def shell(tmp_path):
    instance = Shell(tmp_path)
    yield instance
    instance.close()


def after(seconds, action):
    timer = Timer(seconds, action)
    timer.daemon = True
    timer.start()
    return timer


def real(path):
    return os.path.realpath(path)


def test_runs_a_command_and_shows_the_output_while_it_runs(shell):
    chunks = []
    assert shell.execute("echo hello\necho wrong >&2", emit=chunks.append) == (
        "hello\nwrong\n"
    )
    assert "hello" in "".join(chunks)


def test_state_stays_between_blocks(shell, tmp_path):
    (tmp_path / "sub").mkdir()
    shell.execute(
        "value=41\ncd sub\nalias greet='echo aliased'\nadd() { echo function; }"
    )
    assert shell.execute("echo $value\npwd\ngreet\nadd") == (
        f"41\n{real(tmp_path)}/sub\naliased\nfunction\n"
    )


def test_python_block_runs_a_script_and_removes_the_file(shell):
    output = shell.execute("import sys\n\nprint('from python', sys.argv[0])", "python")
    prefix, path = output.strip().split(" python ")
    assert prefix == "from"
    assert not Path(path).exists()


def test_python_block_reads_the_shell_environment(shell, tmp_path):
    (tmp_path / "sub").mkdir()
    shell.execute("export IMD_TEST_VALUE=visible\ncd sub")
    assert (
        shell.execute(
            "import os\n\nprint(os.environ['IMD_TEST_VALUE'], os.getcwd())", "python"
        )
        == f"visible {real(tmp_path)}/sub\n"
    )


def test_python_block_keeps_no_state(shell):
    shell.execute("value = 1", "python")
    assert "NameError" in shell.execute("print(value)", "python")


def test_unknown_language_reports_an_error(shell):
    with pytest.raises(ValueError, match="sql"):
        shell.execute("select 1", "sql")
    assert shell.execute("echo alive") == "alive\n"


def test_language_tags_ignore_case():
    assert check_language("PYTHON") == "python"
    assert check_language("Shell") == "shell"


def test_py_tag_is_not_python():
    with pytest.raises(ValueError, match="run py blocks"):
        check_language("py")


def test_unsupported_shell_reports_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/opt/homebrew/bin/fish")
    instance = Shell(tmp_path)
    try:
        with pytest.raises(RuntimeError, match="POSIX"):
            instance.execute("echo hello")
    finally:
        instance.close()


def test_interrupt_keeps_the_shell(shell):
    shell.execute("value=kept")
    after(1, shell.interrupt)
    shell.execute("sleep 30")
    assert shell.execute("echo $value") == "kept\n"


def test_kill_reports_the_lost_state_and_starts_a_new_shell(shell):
    shell.execute("value=kept")
    after(1, shell.kill)
    assert shell.execute("sleep 30").endswith("The shell stopped. The state is lost.\n")
    assert shell.execute("echo $value") == "\n"


def test_close_removes_the_files_and_stops_the_shell(shell):
    directory = Path(
        shell.execute("import sys\n\nprint(sys.argv[0])", "python").strip()
    ).parent
    pid = int(shell.execute("echo $$").strip())
    assert directory.is_dir()

    shell.close()

    assert not directory.exists()
    with pytest.raises(OSError):
        os.kill(pid, 0)


def test_close_interrupts_the_command_before_it_stops_the_shell(shell, tmp_path):
    marker = tmp_path / "cleaned"
    code = (
        "import time\n\n"
        "try:\n"
        "    time.sleep(30)\n"
        "except KeyboardInterrupt:\n"
        f"    open({str(marker)!r}, 'w').close()\n"
    )
    worker = Thread(target=shell.execute, args=(code, "python"))
    worker.start()
    sleep(2)

    shell.close()

    worker.join(10)
    assert not worker.is_alive()
    assert marker.exists()


def test_keys_reach_the_terminal(shell):
    after(1, lambda: shell.send("typed\n"))
    assert shell.execute("read value\necho got=$value") == "typed\ngot=typed\n"
