"""Web search tool with a free/local backend chain.

Order of preference: a self-hosted SearXNG (fully private), then the pure-Python
``ddgs`` library (no key), then Tavily (free tier, key required). The agent itself
stays local; only this tool reaches the network, and it is `RiskLevel.NETWORK`
(gated by default). Results carry URLs so the model can follow the mandatory
search → fetch → cite chain.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, runtime_checkable

import httpx
from pydantic import BaseModel

from lca.config.settings import Settings, get_settings
from lca.observability.logging import get_logger
from lca.tools.base import Artifact, RiskLevel, ToolContext, ToolResult, ToolSpec

log = get_logger("tools.web.search")


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""


@runtime_checkable
class SearchBackend(Protocol):
    name: str

    async def search(self, query: str, max_results: int) -> list[SearchResult]: ...


class SearxngBackend:
    name = "searxng"

    def __init__(self, base_url: str) -> None:
        self._url = base_url.rstrip("/")

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{self._url}/search", params={"q": query, "format": "json"})
            resp.raise_for_status()
            data = resp.json()
        out = []
        for r in data.get("results", [])[:max_results]:
            out.append(
                SearchResult(
                    title=r.get("title", ""), url=r.get("url", ""), snippet=r.get("content", "")
                )
            )
        return out


class DdgsBackend:
    name = "ddgs"

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        def _run() -> list[SearchResult]:
            from ddgs import DDGS  # lazy: optional `search` extra

            with DDGS() as ddgs:
                rows = ddgs.text(query, max_results=max_results)
            return [
                SearchResult(
                    title=row.get("title", ""),
                    url=row.get("href", row.get("url", "")),
                    snippet=row.get("body", ""),
                )
                for row in rows
            ]

        return await asyncio.to_thread(_run)


class TavilyBackend:
    name = "tavily"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": self._key, "query": query, "max_results": max_results},
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            SearchResult(
                title=r.get("title", ""), url=r.get("url", ""), snippet=r.get("content", "")
            )
            for r in data.get("results", [])[:max_results]
        ]


def build_backends(settings: Settings | None = None) -> list[SearchBackend]:
    settings = settings or get_settings()
    backends: list[SearchBackend] = []
    if settings.search.searxng_url:
        backends.append(SearxngBackend(settings.search.searxng_url))
    backends.append(DdgsBackend())  # pure-python default
    if settings.search.tavily_api_key:
        backends.append(TavilyBackend(settings.search.tavily_api_key))
    return backends


class WebSearchTool:
    def __init__(
        self, backends: list[SearchBackend] | None = None, *, max_results: int = 5
    ) -> None:
        self._backends = backends if backends is not None else build_backends()
        self._max_results = max_results

    spec = ToolSpec(
        name="web_search",
        description=(
            "Search the web and return titles, URLs and snippets. Follow up with "
            "fetch_url on a result to read and cite its content."
        ),
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query."}},
            "required": ["query"],
        },
        risk=RiskLevel.NETWORK,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        query = str(args["query"]).strip()
        if not query:
            return ToolResult.error("empty query")
        for backend in self._backends:
            try:
                results = await backend.search(query, self._max_results)
            except Exception as exc:
                log.warning("web_search.backend_failed", backend=backend.name, error=str(exc))
                continue
            if results:
                return self._format(results)
        return ToolResult.ok_text("(no search results; check connectivity or configure a backend)")

    @staticmethod
    def _format(results: list[SearchResult]) -> ToolResult:
        lines = [f"{i + 1}. {r.title}\n   {r.url}\n   {r.snippet}" for i, r in enumerate(results)]
        artifacts = [Artifact(kind="citation", title=r.title, uri=r.url) for r in results]
        return ToolResult.ok_text("\n".join(lines), artifacts=artifacts)
