"""llama.cpp `llama-server` provider.

Extends the generic OpenAI-compatible provider with the two things that make
llama.cpp our preferred engine for an anti-hallucination agent:

* **GBNF grammar constraints** — passed via the non-standard ``grammar`` body
  field, which forces tool-call output to be structurally valid;
* **true context window discovery** via the ``/props`` endpoint, so we cap our
  token budget to what the server was actually launched with.
"""

from __future__ import annotations

from typing import Any

import httpx

from lca.observability.logging import get_logger
from lca.providers.base import ChatRequest, ProviderCaps, ProviderHealth
from lca.providers.openai_compat import OpenAICompatProvider

log = get_logger("providers.llamacpp")


class LlamaCppProvider(OpenAICompatProvider):
    """Provider tuned for llama-server (grammar + /props)."""

    name = "llamacpp"

    def capabilities(self) -> ProviderCaps:
        return ProviderCaps(
            supports_grammar=True,
            supports_native_tools=True,
            supports_parallel_tool_calls=True,
        )

    def _build_body(self, req: ChatRequest) -> dict[str, Any]:
        body = super()._build_body(req)
        if req.grammar:
            # llama-server accepts a GBNF grammar string directly.
            body["grammar"] = req.grammar
        return body

    async def health(self) -> ProviderHealth:
        base = await super().health()
        if not base.reachable:
            return base
        # Discover the real context window the server was launched with. `/props` lives
        # under /v1 on LM Studio but at the server root on raw llama-server — try both so
        # discovery works on either engine.
        root = self._base_url.removesuffix("/v1").rstrip("/")
        candidates = [f"{self._base_url}/props", f"{root}/props"]
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for props_url in dict.fromkeys(candidates):  # de-duped, order-preserving
                    resp = await client.get(props_url, headers=self._headers())
                    if resp.status_code < 400:
                        props = resp.json()
                        n_ctx = props.get("default_generation_settings", {}).get(
                            "n_ctx"
                        ) or props.get("n_ctx")
                        if isinstance(n_ctx, int):
                            base.context_window = n_ctx
                        break
        except httpx.HTTPError as exc:
            log.debug("llamacpp.props_unavailable", error=str(exc))
        return base
