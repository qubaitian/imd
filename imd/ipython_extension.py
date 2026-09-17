import ast
import os

import imd

from . import session_api
from .terminal import run_shell


def load_ipython_extension(shell):
    shell.user_ns["imd"] = imd
    session_api._owner_pid = os.getppid()
    shell.system = lambda command: run_shell(shell, command)

    def multiline_automagic(lines):
        source = "".join(lines)
        if not shell.automagic or len(lines) < 2:
            return lines
        tree = ast.parse(source)
        bindings = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
        }
        bindings.update(node.arg for node in ast.walk(tree) if isinstance(node, ast.arg))
        bindings.update(
            node.asname or node.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.alias)
        )
        bindings.update(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        )
        rows = {
            node.lineno - 1
            for node in ast.walk(tree)
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Name)
            and node.value.id not in bindings
        }
        return [
            shell.prefilter_manager.prefilter_line(
                line.rstrip("\n"), continue_prompt=True
            )
            + "\n"
            if index in rows
            else line
            for index, line in enumerate(lines)
        ]

    shell.input_transformers_post.append(multiline_automagic)
