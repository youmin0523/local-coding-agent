"""A scripted, deterministic provider for tests and offline development.

`FakeProvider` is the keystone of the test strategy: because the entire agent
(ReAct loop, permissions, sandbox, verification, event stream) depends only on
the `LLMProvider` interface, replaying scripted `ChatChunk`s here exercises all of
it with zero GPU and perfect determinism.

A "script" is either a list of turns (each turn a list of chunks, consumed in
order) or a callable ``(ChatRequest) -> list[ChatChunk]`` for adaptive fakes
(e.g. responding to the latest tool result, or producing best-of-N variety).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from lca.providers.base import (
    ChatChunk,
    ChatRequest,
    ProviderCaps,
    ProviderHealth,
)

Script = list[list[ChatChunk]] | Callable[[ChatRequest], list[ChatChunk]]


def text_chunks(text: str, *, finish: str = "stop", pieces: int = 3) -> list[ChatChunk]:
    """Split ``text`` into a few streamed deltas, then a finish marker."""
    if not text:
        return [ChatChunk(finish_reason=finish)]
    size = max(1, len(text) // pieces)
    parts = [text[i : i + size] for i in range(0, len(text), size)]
    chunks = [ChatChunk(delta_text=p) for p in parts]
    chunks.append(ChatChunk(finish_reason=finish))
    return chunks


def tool_chunks(
    name: str, arguments: dict[str, object], call_id: str = "call_1"
) -> list[ChatChunk]:
    """Emit a single tool call followed by a tool_calls finish marker."""
    from lca.core.messages import ToolCall

    return [
        ChatChunk(tool_call=ToolCall(id=call_id, name=name, arguments=arguments)),
        ChatChunk(finish_reason="tool_calls"),
    ]


class FakeProvider:
    """An `LLMProvider` that replays a script."""

    name = "fake"

    def __init__(self, script: Script, *, supports_grammar: bool = False) -> None:
        self._script = script
        self._turn = 0
        self._supports_grammar = supports_grammar
        self.requests: list[ChatRequest] = []  # recorded for assertions

    def capabilities(self) -> ProviderCaps:
        return ProviderCaps(
            supports_grammar=self._supports_grammar,
            supports_native_tools=True,
            supports_parallel_tool_calls=False,
        )

    async def health(self) -> ProviderHealth:
        return ProviderHealth(reachable=True, models=["fake"], context_window=16_384)

    async def chat_stream(self, req: ChatRequest) -> AsyncIterator[ChatChunk]:
        self.requests.append(req)
        if callable(self._script):
            chunks = self._script(req)
        else:
            if self._turn >= len(self._script):
                raise AssertionError(
                    f"FakeProvider script exhausted after {self._turn} turns "
                    f"(no scripted response for request #{self._turn + 1})"
                )
            chunks = self._script[self._turn]
            self._turn += 1
        for chunk in chunks:
            yield chunk
