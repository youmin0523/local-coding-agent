"""RetryingProvider: retry pre-stream connection errors, never mid-stream."""

from __future__ import annotations

from collections.abc import AsyncIterator

from lca.core.errors import EngineUnavailableError
from lca.providers.base import ChatChunk, ChatRequest, ProviderCaps, ProviderHealth
from lca.providers.fake import text_chunks
from lca.providers.retry import RetryingProvider


class _Flaky:
    """Fails the connection `fail_times`, then streams normally."""

    name = "flaky"

    def __init__(self, fail_times: int, *, mid_stream: bool = False) -> None:
        self.calls = 0
        self._fail_times = fail_times
        self._mid_stream = mid_stream

    def capabilities(self) -> ProviderCaps:
        return ProviderCaps()

    async def health(self) -> ProviderHealth:
        return ProviderHealth(reachable=True)

    async def chat_stream(self, req: ChatRequest) -> AsyncIterator[ChatChunk]:
        self.calls += 1
        if self.calls <= self._fail_times:
            if self._mid_stream:
                yield ChatChunk(delta_text="partial")  # started → must NOT be retried
            raise EngineUnavailableError("engine warming up")
        for chunk in text_chunks("ok"):
            yield chunk


def _req() -> ChatRequest:
    return ChatRequest(messages=[], model="fake")


async def _drain(provider, req) -> str:
    return "".join([c.delta_text or "" async for c in provider.chat_stream(req)])


async def test_retries_until_success():
    inner = _Flaky(fail_times=2)
    provider = RetryingProvider(inner, attempts=3, backoff_s=0.0)
    text = await _drain(provider, _req())
    assert "ok" in text
    assert inner.calls == 3


async def test_gives_up_after_attempts():
    inner = _Flaky(fail_times=5)
    provider = RetryingProvider(inner, attempts=2, backoff_s=0.0)
    raised = False
    try:
        await _drain(provider, _req())
    except EngineUnavailableError:
        raised = True
    assert raised
    assert inner.calls == 2


async def test_does_not_retry_mid_stream():
    # Once a chunk was yielded, a later failure must propagate (no duplicate output).
    inner = _Flaky(fail_times=1, mid_stream=True)
    provider = RetryingProvider(inner, attempts=3, backoff_s=0.0)
    chunks: list[str] = []
    raised = False
    try:
        async for c in provider.chat_stream(_req()):
            if c.delta_text:
                chunks.append(c.delta_text)
    except EngineUnavailableError:
        raised = True
    assert raised
    assert chunks == ["partial"]  # streamed once, not retried
    assert inner.calls == 1
