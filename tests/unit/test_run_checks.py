"""run_checks: tests are the authoritative correctness oracle; type/lint advisory."""

from __future__ import annotations

from pathlib import Path

from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.permissions.sandbox import SandboxResult
from lca.tools.base import ToolContext
from lca.tools.run_checks import RunChecksTool


class _FakeSandbox:
    """Returns a scripted exit code per tool (pytest/mypy/ruff) found in argv."""

    def __init__(self, codes: dict[str, int]) -> None:
        self._codes = codes

    async def run_command(self, argv: list[str], timeout_s: float = 300.0) -> SandboxResult:
        tool = next((t for t in ("pytest", "mypy", "ruff") if t in argv), "?")
        return SandboxResult(exit_code=self._codes.get(tool, 0), stdout="", stderr="")


def _ctx(ws: Path, sandbox: _FakeSandbox) -> ToolContext:
    return ToolContext(
        workspace_root=ws,
        approver=AutoApprover(),
        session=Session(workspace_root=ws),
        sandbox=sandbox,  # type: ignore[arg-type]
    )


async def test_all_tests_authoritative_lint_advisory(tmp_path: Path):
    # tests pass; lint + typecheck fail -> oracle still OK (style/type are advisory)
    res = await RunChecksTool().run(
        {"kind": "all"}, _ctx(tmp_path, _FakeSandbox({"pytest": 0, "ruff": 1, "mypy": 1}))
    )
    assert res.ok is True


async def test_all_fails_when_tests_fail(tmp_path: Path):
    res = await RunChecksTool().run(
        {"kind": "all"}, _ctx(tmp_path, _FakeSandbox({"pytest": 1, "ruff": 0, "mypy": 0}))
    )
    assert res.ok is False


async def test_no_tests_collected_is_not_a_failure(tmp_path: Path):
    res = await RunChecksTool().run(
        {"kind": "all"}, _ctx(tmp_path, _FakeSandbox({"pytest": 5, "ruff": 1, "mypy": 1}))
    )
    assert res.ok is True
    assert "no tests collected" in res.content


async def test_explicit_single_check_stays_authoritative(tmp_path: Path):
    res = await RunChecksTool().run(
        {"kind": "typecheck"}, _ctx(tmp_path, _FakeSandbox({"mypy": 1}))
    )
    assert res.ok is False
