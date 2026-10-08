import asyncio
import os
import re
import shutil
import signal

import pytest

from imd.sessions import Session, Sessions


async def output_contains(session, expected):
    async with asyncio.timeout(5):
        while expected not in session.snapshot()["output"]:
            await asyncio.sleep(0.01)


async def test_runs_keep_directory_environment_and_python_variables(tmp_path):
    child = tmp_path / "child"
    child.mkdir()
    session = await Session.open(tmp_path)
    try:
        assert (await session.run("cd child\n$IMD_TEST = 'kept'\nanswer = 42"))["status"] == "ok"
        result = await session.run("print(str($PWD) + '|' + $IMD_TEST + '|' + str(answer))")
        assert result["status"] == "ok"
        assert result["cwd"] == str(child)
        await output_contains(session, f"{child}|kept|42")
    finally:
        await session.close()


async def test_worker_uses_the_service_package_instead_of_an_older_install(tmp_path, monkeypatch):
    old = tmp_path / "old-install"
    package = old / "imd"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    monkeypatch.setenv("PYTHONPATH", str(old))
    session = await Session.open(tmp_path)
    try:
        result = await session.run("print('same package')")
        assert result["status"] == "ok"
        assert result["text"] == "same package\n"
    finally:
        await session.close()


async def test_documents_are_isolated_and_reopening_keeps_the_session(tmp_path):
    sessions = Sessions()
    try:
        first = await sessions.get(tmp_path / "first.md")
        second = await sessions.get(tmp_path / "second.md")
        assert await sessions.get(tmp_path / "first.md") is first
        await first.run("$IMD_PRIVATE = 'first'\nprivate_value = 9")
        await second.run(
            "print('isolated=' + str('private_value' not in globals() and 'IMD_PRIVATE' not in __xonsh__.env))"
        )
        await output_contains(second, "isolated=True")
        assert "IMD_PRIVATE" not in os.environ
    finally:
        await sessions.close()


async def test_runs_are_serial_and_errors_do_not_end_the_session(tmp_path):
    session = await Session.open(tmp_path)
    try:
        first = asyncio.create_task(session.run("import time\ntime.sleep(0.1)\nvalue = 7"))
        second = asyncio.create_task(session.run("print('value=' + str(value))"))
        assert all(r["status"] == "ok" for r in await asyncio.gather(first, second))
        await output_contains(session, "value=7")
        assert (await session.run("raise ValueError('expected error')"))["status"] == "error"
        assert (await session.run("print('still alive')"))["status"] == "ok"
        await output_contains(session, "still alive")
    finally:
        await session.close()


async def test_console_accepts_input_and_interrupts_a_run(tmp_path):
    session = await Session.open(tmp_path)
    try:
        run = asyncio.create_task(
            session.run("name = input('Your name: ')\nprint('hello ' + name)")
        )
        await output_contains(session, "Your name:")
        session.write("Ada\n")
        assert (await asyncio.wait_for(run, 5))["status"] == "ok"
        await output_contains(session, "hello Ada")
        run = asyncio.create_task(
            session.run("import time\nprint('waiting', flush=True)\ntime.sleep(30)")
        )
        await output_contains(session, "waiting")
        session.interrupt()
        assert (await asyncio.wait_for(run, 5))["status"] == "interrupted"
        assert (await session.run("print('after interrupt')"))["status"] == "ok"
    finally:
        await session.close()


async def test_reset_replaces_only_one_document_session(tmp_path):
    sessions = Sessions()
    try:
        first = await sessions.get(tmp_path / "first.md")
        second = await sessions.get(tmp_path / "second.md")
        await first.run("value = 1")
        replacement = await sessions.reset(tmp_path / "first.md")
        assert replacement is not first
        assert await sessions.get(tmp_path / "second.md") is second
        await replacement.run("print('fresh=' + str('value' not in globals()))")
        await output_contains(replacement, "fresh=True")
    finally:
        await sessions.close()


async def test_external_commands_stream_accept_input_and_report_failure(tmp_path):
    session = await Session.open(tmp_path)
    try:
        run = asyncio.create_task(
            session.run(
                "python -u -c \"print('external prompt', flush=True); print('received=' + input())\""
            )
        )
        await output_contains(session, "external prompt")
        session.write("test input\n")
        assert (await asyncio.wait_for(run, 5))["status"] == "ok"
        await output_contains(session, "received=test input")
        assert (await session.run("python -c 'import sys; sys.exit(3)'"))["status"] == "error"
        assert (await session.run("print('after failure')"))["status"] == "ok"
    finally:
        await session.close()


async def test_interrupt_external_command_keeps_python_state(tmp_path):
    session = await Session.open(tmp_path)
    try:
        await session.run("value = 42")
        run = asyncio.create_task(
            session.run(
                "python -u -c \"import time; print('external waiting', flush=True); time.sleep(30)\""
            )
        )
        await output_contains(session, "external waiting")
        session.interrupt()
        assert (await asyncio.wait_for(run, 5))["status"] == "interrupted"
        assert (await session.run("print('retained=' + str(value))"))["status"] == "ok"
        await output_contains(session, "retained=42")
    finally:
        await session.close()


async def test_reset_notifies_connections_even_after_the_process_died(tmp_path):
    sessions = Sessions()
    try:
        session = await sessions.get(tmp_path / "guide.md")
        with pytest.raises(RuntimeError, match="process ended"):
            await session.run("import os\nos._exit(2)")
        events = session.subscribe()
        assert (await events.get())["state"] == "closed"
        await sessions.reset(tmp_path / "guide.md")
        assert (await asyncio.wait_for(events.get(), 1))["type"] == "closed"
    finally:
        await sessions.close()


async def test_close_ends_background_commands(tmp_path):
    session = await Session.open(tmp_path)
    pid = None
    try:
        await session.run("sleep 30 &")
        await session.run(
            "print('bgpid=' + str(next(iter(__xonsh__.all_jobs.values()))['pids'][0]))"
        )
        await output_contains(session, "bgpid=")
        pid = int(re.search(r"bgpid=(\d+)", session.snapshot()["output"])[1])
        await session.close()
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    finally:
        await session.close()
        if pid:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


async def test_output_events_and_reconnection_snapshot_are_linked_to_the_run(tmp_path):
    session = await Session.open(tmp_path)
    try:
        events = session.subscribe()
        await session.run("print('first result')", "run-one", "abc123")
        result = await session.run("print('second result')", "run-two", "def456")
        assert result["text"] == "second result\n"
        assert result["block_id"] == "def456"
        outputs = []
        while not events.empty():
            event = events.get_nowait()
            if event["type"] == "output":
                outputs.append(event)
        assert any(
            event["id"] == "run-one" and "first result" in event["data"] for event in outputs
        )
        assert any(
            event["id"] == "run-two" and "second result" in event["data"] for event in outputs
        )
        saved = session.snapshot()["runs"]
        assert saved[0]["block_id"] == "abc123"
        assert saved[1]["text"] == "second result\n"
    finally:
        await session.close()


@pytest.mark.skipif(shutil.which("vim") is None, reason="Vim is not installed.")
async def test_vim_can_edit_a_file_inside_a_run(tmp_path):
    file = tmp_path / "vim.txt"
    session = await Session.open(tmp_path)
    try:
        session.resize(80, 24)
        run = asyncio.create_task(
            session.run("print('before vim')\nvim -Nu NONE -i NONE -n vim.txt\nprint('after vim')")
        )
        await output_contains(session, "\x1b[?1049h")
        session.resize(56, 20)
        session.write("iEdited in Vim\x1b:wq\n")
        result = await asyncio.wait_for(run, 10)
        assert result["status"] == "ok"
        assert file.read_text() == "Edited in Vim\n"
        assert "before vim" in result["text"]
        assert "after vim" in result["text"]
        assert "Edited in Vim" not in result["text"]
    finally:
        await session.close()
