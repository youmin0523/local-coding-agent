"""Web search backend chain + fetch/extract (no real network)."""

from __future__ import annotations

from pathlib import Path

from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.tools.base import ToolContext
from lca.tools.web.fetch import FetchUrlTool, extract_text
from lca.tools.web.search import SearchResult, WebSearchTool


class _Backend:
    def __init__(
        self, name: str, results: list[SearchResult] | None, *, fail: bool = False
    ) -> None:
        self.name = name
        self._results = results or []
        self._fail = fail

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        if self._fail:
            raise RuntimeError("backend down")
        return self._results


def _ctx(ws: Path) -> ToolContext:
    return ToolContext(
        workspace_root=ws, approver=AutoApprover(), session=Session(workspace_root=ws)
    )


async def test_search_returns_results_and_citations(tmp_path: Path):
    backend = _Backend("fake", [SearchResult(title="Py docs", url="https://x", snippet="about py")])
    res = await WebSearchTool([backend]).run({"query": "python"}, _ctx(tmp_path))
    assert res.ok
    assert "https://x" in res.content
    assert any(a.kind == "citation" and a.uri == "https://x" for a in res.artifacts)


async def test_search_fails_over_to_next_backend(tmp_path: Path):
    b1 = _Backend("down", None, fail=True)
    b2 = _Backend("empty", [])
    b3 = _Backend("good", [SearchResult(title="hit", url="https://ok")])
    res = await WebSearchTool([b1, b2, b3]).run({"query": "q"}, _ctx(tmp_path))
    assert "https://ok" in res.content


async def test_search_no_backend_results(tmp_path: Path):
    res = await WebSearchTool([_Backend("empty", [])]).run({"query": "q"}, _ctx(tmp_path))
    assert res.ok and "no search results" in res.content


def test_extract_text_strips_tags_and_scripts():
    html = "<html><head><style>x{}</style></head><body><script>bad()</script><p>Hello world</p></body></html>"
    text = extract_text(html)
    assert "Hello world" in text
    assert "bad()" not in text and "x{}" not in text


async def test_fetch_url_returns_text_and_citation(tmp_path: Path):
    async def fake_fetch(url: str) -> str:
        return "<p>Important content here</p>"

    tool = FetchUrlTool(fetcher=fake_fetch)
    res = await tool.run({"url": "https://example.com"}, _ctx(tmp_path))
    assert res.ok
    assert "Important content here" in res.content
    assert any(a.uri == "https://example.com" for a in res.artifacts)


async def test_fetch_url_rejects_non_http(tmp_path: Path):
    res = await FetchUrlTool().run({"url": "file:///etc/passwd"}, _ctx(tmp_path))
    assert not res.ok
