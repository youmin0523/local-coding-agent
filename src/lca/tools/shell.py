"""Allowlisted shell execution.

There is deliberately no generic "run any shell string" capability and no shell
MCP server. Commands run through the `SandboxRunner` (no shell interpolation,
timeout, scrubbed env) and the executable must be on an allowlist. This is
`RiskLevel.SHELL`, so it is gated by default.
"""

from __future__ import annotations

import shlex
from pathlib import PurePath
from typing import Any

from lca.core.errors import SandboxError
from lca.tools.base import Artifact, RiskLevel, ToolContext, ToolResult, ToolSpec

# Conservative defaults; extendable via settings later. Matched on the basename
# without extension, case-insensitively.
DEFAULT_ALLOWLIST = frozenset(
    {
        "python",
        "python3",
        "py",
        "pip",
        "uv",
        "pytest",
        "ruff",
        "mypy",
        "pyright",
        "node",
        "npm",
        "npx",
        "git",
        "echo",
        "ls",
        "dir",
        "cat",
        "type",
        "where",
        "which",
        "go",
        "cargo",
        "rustc",
        "java",
        "javac",
        "dotnet",
    }
)


class RunShellTool:
    def __init__(self, allowlist: frozenset[str] = DEFAULT_ALLOWLIST) -> None:
        self._allowlist = allowlist

    spec = ToolSpec(
        name="run_shell",
        description=(
            "Run an allowlisted command (e.g. python, pytest, git, npm) in the workspace "
            "sandbox and return its exit code, stdout and stderr."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command line, e.g. 'python script.py' or 'pytest -q'.",
                },
            },
            "required": ["command"],
        },
        risk=RiskLevel.SHELL,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        command = str(args["command"]).strip()
        if not command:
            return ToolResult.error("empty command")
        try:
            argv = shlex.split(command, posix=False)
        except ValueError as exc:
            return ToolResult.error(f"could not parse command: {exc}")
        # Strip surrounding quotes shlex leaves on Windows-style tokens.
        argv = [tok.strip('"') for tok in argv]
        executable = PurePath(argv[0]).stem.lower()
        if executable not in self._allowlist:
            return ToolResult.error(
                f"'{executable}' is not on the shell allowlist. Allowed: "
                f"{', '.join(sorted(self._allowlist))}."
            )
        if ctx.sandbox is None:
            return ToolResult.error("no sandbox available for shell execution")
        try:
            result = await ctx.sandbox.run_command(argv)
        except SandboxError as exc:
            return ToolResult.error(str(exc))

        status = "timed out" if result.timed_out else f"exit {result.exit_code}"
        body = f"$ {command}\n[{status}, {result.duration_s}s]\n"
        if result.stdout:
            body += f"\n--- stdout ---\n{result.stdout}"
        if result.stderr:
            body += f"\n--- stderr ---\n{result.stderr}"
        return ToolResult(
            ok=result.ok,
            content=body,
            artifacts=[Artifact(kind="output", title=command, body=body)],
        )
