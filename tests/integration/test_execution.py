"""The execution oracle: run_python sandbox and run_checks (pytest) ground truth."""

from __future__ import annotations

from pathlib import Path

from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.permissions.sandbox import SandboxRunner
from lca.tools.base import ToolContext
from lca.tools.code_exec import RunPythonTool
from lca.tools.run_checks import RunChecksTool


def _ctx(ws: Path, *, sandbox: SandboxRunner | None = None) -> ToolContext:
    return ToolContext(
        workspace_root=ws,
        approver=AutoApprover(),
        session=Session(workspace_root=ws),
        sandbox=sandbox,
    )


async def test_run_python_captures_stdout(tmp_path: Path):
    res = await RunPythonTool().run({"code": "print('hello', 6 * 7)"}, _ctx(tmp_path))
    assert res.ok
    assert "hello 42" in res.content


async def test_run_python_reports_failure(tmp_path: Path):
    res = await RunPythonTool().run({"code": "raise ValueError('boom')"}, _ctx(tmp_path))
    assert not res.ok
    assert "ValueError" in res.content and "boom" in res.content


async def test_run_python_can_import_workspace_module(tmp_path: Path):
    # Regression: the snippet runs from a temp dir, so the workspace must be on
    # PYTHONPATH for `import <workspace module>` to work (found via live test).
    (tmp_path / "mymod.py").write_text("VALUE = 7\n", "utf-8")
    res = await RunPythonTool().run(
        {"code": "import mymod; print(mymod.VALUE * 6)"}, _ctx(tmp_path)
    )
    assert res.ok
    assert "42" in res.content


async def test_run_checks_passing_tests_are_ground_truth(tmp_path: Path):
    (tmp_path / "test_sample.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n", "utf-8")
    ctx = _ctx(tmp_path, sandbox=SandboxRunner(tmp_path, timeout_s=120))
    res = await RunChecksTool().run({"kind": "tests"}, ctx)
    assert res.is_truth  # the verification gate trusts execution results
    assert res.ok
    assert "tests: PASS" in res.content


async def test_run_checks_failing_tests_report_fail(tmp_path: Path):
    (tmp_path / "test_bad.py").write_text("def test_bad():\n    assert 1 == 2\n", "utf-8")
    ctx = _ctx(tmp_path, sandbox=SandboxRunner(tmp_path, timeout_s=120))
    res = await RunChecksTool().run({"kind": "tests"}, ctx)
    assert not res.ok
    assert "tests: FAIL" in res.content
