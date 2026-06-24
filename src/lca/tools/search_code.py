"""The `search_code` tool — RAG retrieval exposed to the model.

A `RiskLevel.READ` tool that returns citeable ``path:start-end`` snippets, so the
model can ground answers about the codebase in real, retrieved code rather than
guessing. Wraps any `Retriever`.
"""

from __future__ import annotations

from typing import Any

from lca.rag.retriever import Retriever
from lca.tools.base import Artifact, RiskLevel, ToolContext, ToolResult, ToolSpec


class SearchCodeTool:
    def __init__(self, retriever: Retriever, *, default_k: int = 6) -> None:
        self._retriever = retriever
        self._default_k = default_k

    spec = ToolSpec(
        name="search_code",
        description=(
            "Search the indexed workspace by meaning and keywords. Returns the most "
            "relevant code snippets with their file:line locations for citation."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for."},
            },
            "required": ["query"],
        },
        risk=RiskLevel.READ,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        query = str(args["query"]).strip()
        if not query:
            return ToolResult.error("empty query")
        chunks = await self._retriever.retrieve(query, self._default_k)
        if not chunks:
            return ToolResult.ok_text(
                "(no results — the workspace may not be indexed yet; run `lca index`.)"
            )
        body = "\n\n".join(c.render() for c in chunks)
        artifacts = [
            Artifact(kind="citation", title=f"{c.path}:{c.start_line}-{c.end_line}", uri=c.path)
            for c in chunks
        ]
        return ToolResult.ok_text(body, artifacts=artifacts)
