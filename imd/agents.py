"""Agent configuration and prompt dispatch for one document session."""

import re
import shlex
from collections.abc import Callable


class AgentCommands:
    def __init__(self):
        self._commands: dict[str, list[str]] = {}
        self._started = False

    def execute(self, code: str, language: str, run_command: Callable[[list[str]], None]) -> bool:
        """Handle sh configuration or an agent prompt, returning False for ordinary code."""
        lines = [
            line.strip() for line in code.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if language == "sh" and lines and re.match(r"^imd\s+set\s+agent(?:\s|$)", lines[0]):
            commands = {}
            for line in lines:
                words = shlex.split(line, comments=True)
                if (
                    len(words) < 5
                    or words[:3] != ["imd", "set", "agent"]
                    or words[3] not in {"first", "continue"}
                    or not words[4]
                ):
                    raise ValueError(
                        "Use imd set agent first PROGRAM [ARGUMENTS] or "
                        "imd set agent continue PROGRAM [ARGUMENTS]."
                    )
                commands[words[3]] = words[4:]
            self._commands.update(commands)
            if "first" in commands:
                self._started = False
            print("Agent commands configured for this session.", flush=True)
            return True
        if language != "agent":
            return False
        if set(self._commands) != {"first", "continue"}:
            raise ValueError("Configure both first and continue agent commands before a prompt.")
        if not code.strip():
            raise ValueError("The prompt is empty.")
        command = self._commands["continue" if self._started else "first"]
        run_command([*command, code])
        self._started = True
        return True
