"""Resilience wrapper: retry transient engine failures before a stream starts.

Local engines (LM Studio / llama-server) are sometimes briefly unavailable — still
loading a model, just (re)started, momentarily busy. This decorator retries the
*connection phase* with backoff. It never retries once tokens have started flowing
(that would duplicate output), so mid-stream failures propagate as-is.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from lca.core.errors import EngineUnavailableError, ProviderError
from lca.observability.logging import get_logger
from lca.providers.base import ChatChunk, ChatRequest, LLMProvider, ProviderCaps, ProviderHealth

log = get_logger("providers.retry")


class RetryingProvider:
    """Wraps any `LLMProvider`, retrying pre-stream connection errors."""

    def __init__(self, inner: LLMProvider, *, attempts: int = 3, backoff_s: float = 0.5) -> None:
        self._inner = inner
        self._attempts = max(1, attempts)
        self._backoff = backoff_s
        self.name = f"retry({inner.name})"

    def capabilities(self) -> ProviderCaps:
        return self._inner.capabilities()

    async def health(self) -> ProviderHealth:
        return await self._inner.health()

    async def chat_stream(self, req: ChatRequest) -> AsyncIterator[ChatChunk]:
        for attempt in range(self._attempts):
            started = False
            try:
                async for chunk in self._inner.chat_stream(req):
                    started = True
                    yield chunk
                return
            except (EngineUnavailableError, ProviderError) as exc:
                if started or attempt == self._attempts - 1:
                    raise
                delay = self._backoff * (attempt + 1)
                log.warning("provider.retry", attempt=attempt + 1, error=str(exc), delay_s=delay)
                await asyncio.sleep(delay)
