"""The local reference catalog + reference_docs tool."""

from __future__ import annotations

from pathlib import Path

from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.references.catalog import load_catalog, search_catalog
from lca.tools.base import ToolContext
from lca.tools.reference import ReferenceDocsTool


def _ctx(ws: Path) -> ToolContext:
    return ToolContext(workspace_root=ws, approver=AutoApprover(), session=Session(workspace_root=ws))


def test_catalog_loads():
    cat = load_catalog()
    assert len(cat) >= 5
    techs = {e.tech.lower() for e in cat}
    assert any("fastapi" in t for t in techs)


def test_search_ranks_fastapi_first():
    hits = search_catalog("fastapi")
    assert hits and "fastapi" in hits[0].tech.lower()


def test_search_finds_react_hooks():
    hits = search_catalog("react hooks")
    assert any("hook" in h.tech.lower() for h in hits)


async def test_reference_tool_returns_official_docs(tmp_path: Path):
    res = await ReferenceDocsTool().run({"tech": "fastapi"}, _ctx(tmp_path))
    assert res.ok
    assert "fastapi.tiangolo.com" in res.content
    assert any(a.kind == "citation" for a in res.artifacts)


async def test_reference_tool_unknown_tech_suggests_web(tmp_path: Path):
    res = await ReferenceDocsTool().run({"tech": "zxqw-nonexistent"}, _ctx(tmp_path))
    assert res.ok
    assert "web_search" in res.content
