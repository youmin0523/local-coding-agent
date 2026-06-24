"""Execute a Python snippet in an isolated, no-network sandbox.

`RiskLevel.SHELL` (gated by default). Unlike `run_shell`, this always runs with
network disabled by default and in a private temp file, so the model can try code
out without it being able to phone home. Output is returned for the model to read.
"""

from __future__ import annotations

from typing import Any

from lca.permissions.sandbox import SandboxRunner
from lca.tools.base import Artifact, RiskLevel, ToolContext, ToolResult, ToolSpec


class RunPythonTool:
    spec = ToolSpec(
        name="run_python",
        description=(
            "Execute a short Python snippet in an isolated sandbox (network disabled) "
            "and return its stdout, stderr, and exit code."
        ),
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source to execute."},
            },
            "required": ["code"],
        },
        risk=RiskLevel.SHELL,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        code = str(args["code"])
        # Dedicated sandbox so code execution is always network-isolated by default,
        # independent of the agent's shared sandbox settings.
        sandbox = SandboxRunner(ctx.workspace_root, timeout_s=60.0, no_network=True)
        result = await sandbox.run_python(code)
        status = "timed out" if result.timed_out else f"exit {result.exit_code}"
        body = f"[{status}, {result.duration_s}s]\n"
        if result.stdout:
            body += f"\n--- stdout ---\n{result.stdout}"
        if result.stderr:
            body += f"\n--- stderr ---\n{result.stderr}"
        return ToolResult(
            ok=result.ok,
            content=body,
            artifacts=[Artifact(kind="output", title="run_python", body=body)],
        )
