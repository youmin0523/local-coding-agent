"""Fetch a URL and extract readable text, with a citation artifact.

This is the second half of the mandatory search → fetch → cite chain: the model
must fetch a page to ground a web claim, and the returned `Artifact` records the
source URL so the answer can cite it. `RiskLevel.NETWORK`.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from lca.tools.base import Artifact, RiskLevel, ToolContext, ToolResult, ToolSpec

_MAX_CHARS = 12_000
Fetcher = Callable[[str], Awaitable[str]]


async def _default_fetch(url: str) -> str:
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "lca-agent/0.1"})
        resp.raise_for_status()
        content: str = resp.text
        return content


def extract_text(html: str) -> str:
    """Best-effort main-text extraction (trafilatura if available, else strip tags)."""
    try:
        import trafilatura  # optional `search` extra

        extracted: str | None = trafilatura.extract(html)
        if extracted:
            return extracted
    except Exception:
        pass
    no_script = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", no_script)
    return re.sub(r"\s+", " ", text).strip()


class FetchUrlTool:
    def __init__(self, fetcher: Fetcher | None = None) -> None:
        self._fetch = fetcher or _default_fetch

    spec = ToolSpec(
        name="fetch_url",
        description="Fetch a web page and return its readable text (for citing a source).",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string", "description": "The URL to fetch."}},
            "required": ["url"],
        },
        risk=RiskLevel.NETWORK,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        url = str(args["url"]).strip()
        if not url.lower().startswith(("http://", "https://")):
            return ToolResult.error("url must start with http:// or https://")
        try:
            html = await self._fetch(url)
        except Exception as exc:
            return ToolResult.error(f"failed to fetch {url}: {exc}")
        text = extract_text(html)
        if len(text) > _MAX_CHARS:
            text = text[:_MAX_CHARS] + "\n…[truncated]"
        return ToolResult.ok_text(
            f"Source: {url}\n\n{text}",
            artifacts=[Artifact(kind="citation", title=url, uri=url)],
        )
