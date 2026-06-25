"""`reference_docs` — look up official docs + how-to for a language/framework.

Lets the agent apply *any* technology: it consults the local, cited reference
catalog first (offline, grounded), and the description nudges it to follow up with
`fetch_url` on the official link for live detail when needed. `RiskLevel.READ`.
"""

from __future__ import annotations

from typing import Any

from lca.references.catalog import search_catalog
from lca.tools.base import Artifact, RiskLevel, ToolContext, ToolResult, ToolSpec


class ReferenceDocsTool:
    spec = ToolSpec(
        name="reference_docs",
        description=(
            "Look up official documentation and how-to idioms for a language, framework, "
            "or tool (e.g. 'fastapi', 'react hooks', 'sqlalchemy'). Returns the official docs "
            "URL + quickstart + key idioms. Use fetch_url on the returned link for live detail."
        ),
        parameters={
            "type": "object",
            "properties": {
                "tech": {"type": "string", "description": "Technology/keyword to look up."},
            },
            "required": ["tech"],
        },
        risk=RiskLevel.READ,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        query = str(args["tech"]).strip()
        if not query:
            return ToolResult.error("empty tech")
        hits = search_catalog(query, limit=3)
        if not hits:
            return ToolResult.ok_text(
                f"(no local reference for '{query}'. Use web_search then fetch_url to read the "
                "official docs and cite them.)"
            )
        body = "\n\n".join(h.render() for h in hits)
        artifacts = [
            Artifact(kind="citation", title=h.tech, uri=h.official_docs)
            for h in hits
            if h.official_docs
        ]
        return ToolResult.ok_text(body, artifacts=artifacts)
