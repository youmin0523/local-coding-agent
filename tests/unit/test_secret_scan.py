"""secret_scan: detect hardcoded secrets, ignore env usage/placeholders, audit .gitignore."""

from __future__ import annotations

from pathlib import Path

from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.tools.base import ToolContext
from lca.tools.secret_scan import SecretScanTool


def _ctx(ws: Path) -> ToolContext:
    return ToolContext(
        workspace_root=ws, approver=AutoApprover(), session=Session(workspace_root=ws)
    )


async def test_detects_hardcoded_key(tmp_path: Path):
    (tmp_path / "conf.py").write_text('SECRET_KEY = "sk-ant-aBcD1234EfGh5678IjKlMnOp"\n', "utf-8")
    res = await SecretScanTool().run({}, _ctx(tmp_path))
    assert not res.ok
    assert "conf.py" in res.content


async def test_ignores_env_usage_and_placeholders(tmp_path: Path):
    (tmp_path / "conf.py").write_text(
        'import os\napi_key = os.environ["API_KEY"]\ntoken = "your-token-here"\n', "utf-8"
    )
    (tmp_path / ".gitignore").write_text(
        ".env\n*.pem\n*.key\n__pycache__/\n.venv/\nnode_modules/\n", "utf-8"
    )
    res = await SecretScanTool().run({}, _ctx(tmp_path))
    assert res.ok
    assert "No hardcoded secrets" in res.content
    assert "covers" in res.content


async def test_flags_env_file_not_ignored(tmp_path: Path):
    (tmp_path / ".env").write_text("SECRET=abc123\n", "utf-8")  # present, no .gitignore
    res = await SecretScanTool().run({}, _ctx(tmp_path))
    assert "No .gitignore" in res.content
    assert ".env" in res.content


async def test_flags_missing_env_in_gitignore(tmp_path: Path):
    (tmp_path / ".env").write_text("SECRET=abc\n", "utf-8")
    (tmp_path / ".gitignore").write_text("__pycache__/\n", "utf-8")  # missing .env
    res = await SecretScanTool().run({}, _ctx(tmp_path))
    assert "missing recommended entries" in res.content
    assert ".env" in res.content
