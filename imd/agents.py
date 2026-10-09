"""Agent configuration and prompt dispatch for one document session."""

import re
import shlex
from collections.abc import Callable


class AgentError(ValueError):
    """Invalid agent configuration or prompt."""


class AgentCommands:
    def __init__(self):
        self._commands: dict[str, list[str]] = {}
        self._started = False
        self._stderr: str | None = None

    def execute(
        self, code: str, language: str,
        run_command: Callable[[list[str | tuple[str, str]]], None],
    ) -> bool:
        """Handle sh configuration or an agent prompt, returning False for ordinary code."""
        lines = [
            line.strip() for line in code.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if language == "sh" and lines and re.match(r"^imd\s+set\s+agent(?:\s|$)", lines[0]):
            commands = {}
            stderr = self._stderr
            for line in lines:
                try:
                    words = shlex.split(line, comments=True)
                except ValueError as error:
                    raise AgentError(f"Cannot read agent configuration: {error}.") from None
                if words[:4] == ["imd", "set", "agent", "stderr"]:
                    if len(words) > 5 or (len(words) == 5 and not words[4]):
                        raise AgentError("Use imd set agent stderr [PATH].")
                    stderr = words[4] if len(words) == 5 else None
                    continue
                if (
                    len(words) < 5
                    or words[:3] != ["imd", "set", "agent"]
                    or words[3] not in {"first", "continue"}
                    or not words[4]
                ):
                    raise AgentError(
                        "Use imd set agent first PROGRAM [ARGUMENTS] or "
                        "imd set agent continue PROGRAM [ARGUMENTS] or "
                        "imd set agent stderr [PATH]."
                    )
                commands[words[3]] = words[4:]
            self._commands.update(commands)
            self._stderr = stderr
            if "first" in commands:
                self._started = False
            print("Agent commands configured for this session.", flush=True)
            return True
        if language != "agent":
            return False
        if set(self._commands) != {"first", "continue"}:
            raise AgentError("Configure both first and continue agent commands before a prompt.")
        if not code.strip():
            raise AgentError("The prompt is empty.")
        command = self._commands["continue" if self._started else "first"]
        arguments: list[str | tuple[str, str]] = [*command, code]
        if self._stderr is not None:
            arguments.append(("2>", self._stderr))
        run_command(arguments)
        self._started = True
        return True
