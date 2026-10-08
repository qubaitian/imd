import asyncio
import json
import shlex
import sys

import pytest

from imd.sessions import Session, Sessions


@pytest.fixture
def agent(tmp_path):
    script = tmp_path / "test agent.py"
    log = tmp_path / "calls.jsonl"
    script.write_text(
        "import json, os, sys, time\n"
        f"with open({str(log)!r}, 'a') as log:\n"
        "    log.write(json.dumps({'args': sys.argv[1:], 'cwd': os.getcwd(), "
        "'env': os.getenv('IMD_AGENT_TEST')}) + '\\n')\n"
        "print('agent reply', flush=True)\n"
        "print('agent progress: ' + sys.argv[-1].strip(), file=sys.stderr, flush=True)\n"
        "if sys.argv[-1].strip() == 'fail': sys.exit(3)\n"
        "if sys.argv[-1].strip() == 'wait': time.sleep(30)\n"
        "if sys.argv[-1].strip() == 'input': print('received=' + input(), flush=True)\n"
    )
    command = shlex.join([sys.executable, "-u", str(script)])
    config = f"imd set agent first {command} first\nimd set agent continue {command} continue\n"

    def calls():
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    return config, calls


async def configure(session, config):
    result = await session.run(config, language="sh")
    assert result["status"] == "ok", result["text"]


async def test_prompts_keep_literal_text_and_switch_to_continue_after_success(tmp_path, agent):
    config, calls = agent
    session = await Session.open(tmp_path)
    try:
        await configure(session, config)
        prompt = "请审核 'quoted' \"text\"\n$(touch injected); $HOME `echo hi`\n"
        first = await session.run(prompt, language="agent")
        second = await session.run("What did I ask?\n", language="agent")
        assert first["status"] == second["status"] == "ok"
        assert first["text"] == f"agent reply\nagent progress: {prompt.strip()}\n"
        assert [call["args"] for call in calls()] == [
            ["first", prompt], ["continue", "What did I ask?\n"],
        ]
        assert not (tmp_path / "injected").exists()
    finally:
        await session.close()


async def test_agent_blocks_keep_configuration_examples_as_prompt_text(tmp_path, agent):
    config, calls = agent
    session = await Session.open(tmp_path)
    try:
        await configure(session, config)
        prompts = [
            "解释一下\n" + config + "这是怎么实现的\n",
            config,
        ]
        for prompt in prompts:
            result = await session.run(prompt, language="agent")
            assert result["status"] == "ok", result["text"]
        assert [call["args"] for call in calls()] == [
            ["first", prompts[0]], ["continue", prompts[1]],
        ]
        result = await session.run("print('ordinary sh')", language="sh")
        assert result["text"] == "ordinary sh\n"
        assert len(calls()) == 2
    finally:
        await session.close()


async def test_agent_blocks_require_configuration_instead_of_executing_code(tmp_path):
    session = await Session.open(tmp_path)
    try:
        result = await session.run("print('must not execute')", language="agent")
        assert result["status"] == "error"
        assert "Configure both first and continue" in result["text"]
        assert result["text"] != "must not execute\n"
    finally:
        await session.close()


async def test_prompts_use_current_directory_and_environment_and_leave_code_available(
    tmp_path, agent
):
    config, calls = agent
    (tmp_path / "child").mkdir()
    session = await Session.open(tmp_path)
    try:
        assert (await session.run("print('before config')", language="sh"))["status"] == "ok"
        await configure(session, config)
        result = await session.run("cd child\n$IMD_AGENT_TEST = 'kept'", language="xonsh")
        assert result["status"] == "ok"
        result = await session.run("print(42)", language="py")
        assert result["text"] == "42\n"
        await session.run("Review this directory", language="agent")
        assert calls()[0]["cwd"] == str(tmp_path / "child")
        assert calls()[0]["env"] == "kept"
    finally:
        await session.close()


async def test_failed_prompts_keep_the_command_choice_and_reconfiguration_starts_again(
    tmp_path, agent
):
    config, calls = agent
    session = await Session.open(tmp_path)
    try:
        await configure(session, config)
        assert (await session.run("fail", language="agent"))["status"] == "error"
        assert (await session.run("retry", language="agent"))["status"] == "ok"
        assert (await session.run("fail", language="agent"))["status"] == "error"
        assert (await session.run("retry", language="agent"))["status"] == "ok"
        await configure(session, config)
        await session.run("new conversation", language="agent")
        assert [call["args"][0] for call in calls()] == [
            "first", "first", "continue", "continue", "first",
        ]
    finally:
        await session.close()


async def test_agent_console_streams_accepts_input_and_interrupts_without_advancing(
    tmp_path, agent
):
    config, calls = agent
    session = await Session.open(tmp_path)
    try:
        await configure(session, config)
        run = asyncio.create_task(session.run("wait", language="agent"))
        async with asyncio.timeout(5):
            while "agent reply" not in session.snapshot()["output"]:
                await asyncio.sleep(0.01)
        session.interrupt()
        assert (await asyncio.wait_for(run, 5))["status"] == "interrupted"
        run = asyncio.create_task(session.run("input", language="agent"))
        async with asyncio.timeout(5):
            while len(calls()) < 2:
                await asyncio.sleep(0.01)
        session.write("Ada\n")
        result = await asyncio.wait_for(run, 5)
        assert result["status"] == "ok"
        assert "received=Ada" in result["text"]
        assert [call["args"][0] for call in calls()] == ["first", "first"]
    finally:
        await session.close()


@pytest.mark.parametrize("invalid", [
    "imd set agent first", "imd set agent wrong program",
    "imd set agent first 'unclosed", "print('mixed code')",
])
async def test_invalid_configuration_is_atomic_and_does_not_become_a_prompt(
    tmp_path, agent, invalid
):
    config, calls = agent
    session = await Session.open(tmp_path)
    try:
        await configure(session, config)
        await session.run("hello", language="agent")
        result = await session.run(config + invalid + "\n", language="sh")
        assert result["status"] == "error"
        assert len(calls()) == 1
        await session.run("still configured", language="agent")
        assert calls()[-1]["args"][0] == "continue"
    finally:
        await session.close()


async def test_incomplete_configuration_and_empty_prompts_report_clear_errors(tmp_path, agent):
    config, calls = agent
    session = await Session.open(tmp_path)
    try:
        await configure(session, config.splitlines()[0])
        result = await session.run("hello", language="agent")
        assert result["status"] == "error"
        assert "Configure both first and continue" in result["text"]
        await configure(session, config)
        result = await session.run(" \n", language="agent")
        assert result["status"] == "error"
        assert "The prompt is empty" in result["text"]
        assert calls() == []
    finally:
        await session.close()


async def test_agent_configuration_is_shared_per_document_and_cleared_by_reset(tmp_path, agent):
    config, calls = agent
    sessions = Sessions()
    try:
        first = await sessions.get(tmp_path / "first.md")
        await configure(first, "# Commands\n\n" + config + "imd set agent stderr shared.log\n")
        reopened = await sessions.get(tmp_path / "first.md")
        result = await reopened.run("hello", language="agent")
        assert result["text"] == "agent reply\n"
        assert (tmp_path / "shared.log").read_text() == "agent progress: hello\n"
        second = await sessions.get(tmp_path / "second.md")
        assert (await second.run("print('code')", language="sh"))["text"] == "code\n"
        replacement = await sessions.reset(tmp_path / "first.md")
        assert (await replacement.run("print('fresh')", language="sh"))["text"] == "fresh\n"
        await configure(replacement, config)
        result = await replacement.run("hello again", language="agent")
        assert "agent progress: hello again" in result["text"]
        assert (tmp_path / "shared.log").read_text() == "agent progress: hello\n"
        assert [call["args"][0] for call in calls()] == ["first", "first"]
    finally:
        await sessions.close()


async def test_agent_stderr_log_keeps_stdout_and_overwrites_for_each_command(tmp_path, agent):
    config, calls = agent
    session = await Session.open(tmp_path)
    try:
        await configure(session, config + "imd set agent stderr 'agent log.txt'\n")
        for prompt in ["first prompt", "later prompt", "fail", "retry"]:
            result = await session.run(prompt, language="agent")
            assert result["status"] == ("error" if prompt == "fail" else "ok")
            assert "agent reply" in result["text"]
            assert "agent progress" not in result["text"]
            assert (tmp_path / "agent log.txt").read_text() == f"agent progress: {prompt}\n"
        assert [call["args"][0] for call in calls()] == [
            "first", "continue", "continue", "continue",
        ]
    finally:
        await session.close()


async def test_agent_stderr_configuration_uses_current_directory_and_can_be_cleared(tmp_path, agent):
    config, calls = agent
    (tmp_path / "child").mkdir()
    session = await Session.open(tmp_path)
    try:
        await configure(session, config)
        await configure(session, "imd set agent stderr codex.log")
        await session.run("cd child", language="sh")
        result = await session.run("hello", language="agent")
        assert "agent progress" not in result["text"]
        assert (tmp_path / "child" / "codex.log").read_text() == "agent progress: hello\n"
        assert not (tmp_path / "codex.log").exists()
        ordinary = await session.run("import sys; print('ordinary error', file=sys.stderr)")
        assert ordinary["text"] == "ordinary error\n"
        await configure(session, "imd set agent stderr")
        result = await session.run("visible", language="agent")
        assert "agent progress: visible" in result["text"]
        assert [call["args"][0] for call in calls()] == ["first", "continue"]
    finally:
        await session.close()


async def test_invalid_agent_stderr_configuration_preserves_commands_and_log(tmp_path, agent):
    config, calls = agent
    session = await Session.open(tmp_path)
    try:
        await configure(session, config + "imd set agent stderr kept.log\n")
        await session.run("hello", language="agent")
        for invalid in ["imd set agent stderr one two", "imd set agent stderr ''"]:
            result = await session.run(config + "imd set agent stderr lost.log\n" + invalid,
                                       language="sh")
            assert result["status"] == "error"
            result = await session.run("kept", language="agent")
            assert "agent progress" not in result["text"]
            assert (tmp_path / "kept.log").read_text() == "agent progress: kept\n"
            assert calls()[-1]["args"][0] == "continue"
        assert not (tmp_path / "lost.log").exists()
    finally:
        await session.close()


async def test_agent_stderr_log_open_failure_does_not_advance_command(tmp_path, agent):
    config, calls = agent
    session = await Session.open(tmp_path)
    try:
        await configure(session, config + "imd set agent stderr missing/codex.log\n")
        result = await session.run("hello", language="agent")
        assert result["status"] == "error"
        assert "missing/codex.log" in result["text"]
        assert calls() == []
        await configure(session, "imd set agent stderr")
        await session.run("retry", language="agent")
        assert calls()[0]["args"][0] == "first"
    finally:
        await session.close()
