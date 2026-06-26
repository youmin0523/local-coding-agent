"""The execution oracle: run tests / type-checker / linter and report results.

This is the least-gameable signal the agent has — the verification gate (M8)
treats its output as ground truth (``is_truth=True``) rather than model belief.
`RiskLevel.SHELL`, gated by default. Commands run via the current interpreter
(`python -m pytest|mypy|ruff`) so they use the project's installed tools.
"""

from __future__ import annotations

import sys
from typing import Any

from lca.permissions.sandbox import SandboxResult, SandboxRunner
from lca.tools.base import RiskLevel, ToolContext, ToolResult, ToolSpec

_CHECKS = {
    "tests": [sys.executable, "-m", "pytest", "-q"],
    "typecheck": [sys.executable, "-m", "mypy"],
    "lint": [sys.executable, "-m", "ruff", "check"],
}


class RunChecksTool:
    spec = ToolSpec(
        name="run_checks",
        description=(
            "Run the project's tests, type-checker, and/or linter and report pass/fail. "
            "Use this to VERIFY changes — its result is authoritative, unlike reasoning."
        ),
        parameters={
            "type": "object",
            "properties": {
                "kind": {
                    "enum": ["tests", "typecheck", "lint", "all"],
                    "description": "Which check to run (default: all).",
                },
                "target": {"type": "string", "description": "Optional path/args to pass."},
            },
        },
        risk=RiskLevel.SHELL,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        kind = str(args.get("kind", "all"))
        target = str(args.get("target", "")).strip()
        selected = list(_CHECKS) if kind == "all" else [kind]
        if kind not in (*_CHECKS, "all"):
            return ToolResult.error(f"unknown check kind: {kind}")

        sandbox = ctx.sandbox or SandboxRunner(ctx.workspace_root, timeout_s=300.0)
        sections: list[str] = []
        per_ok: dict[str, bool] = {}
        for check in selected:
            argv = list(_CHECKS[check])
            if target:
                argv.append(target)
            result = await sandbox.run_command(argv, timeout_s=300.0)
            # pytest exit code 5 = "no tests collected" — nothing to verify, NOT a failure.
            ok = result.ok or (check == "tests" and result.exit_code == 5)
            per_ok[check] = ok
            sections.append(self._summarize(check, result, ok))

        # Correctness oracle: tests are authoritative. In an "all" run, type/lint are
        # advisory (shown, but a style/config nit must NOT force the verification gate to
        # reject logically-correct, test-passing code). Run a single check on its own and
        # it stays authoritative.
        oracle_ok = (
            per_ok["tests"] if ("tests" in per_ok and len(per_ok) > 1) else all(per_ok.values())
        )

        return ToolResult(
            ok=oracle_ok,
            content="\n\n".join(sections),
            is_truth=True,  # execution result — the verification gate trusts this
        )

    @staticmethod
    def _summarize(check: str, result: SandboxResult, ok: bool) -> str:
        if check == "tests" and not result.ok and result.exit_code == 5:
            verdict = "PASS (no tests collected)"
        else:
            verdict = "PASS" if ok else ("TIMEOUT" if result.timed_out else "FAIL")
        output = (result.stdout + "\n" + result.stderr).strip()
        tail = "\n".join(output.splitlines()[-30:])
        return f"### {check}: {verdict} (exit {result.exit_code}, {result.duration_s}s)\n{tail}"
