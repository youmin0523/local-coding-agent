"""The LLM provider seam.

`LLMProvider` is the single interface the agent loop depends on, so the concrete
engine (llama.cpp / Ollama / a fake for tests) is swappable behind it. Providers
stream `ChatChunk`s; the loop assembles text deltas and tool-call deltas itself.

Two engine quirks are normalized *below* this interface so the loop never sees
them (both are real llama.cpp behaviors):
  * tool-call ``arguments`` arriving as a JSON object instead of a JSON string;
  * grammar-constrained decoding being available only on some engines (exposed
    via ``capabilities().supports_grammar``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from lca.core.messages import Message, ToolCall


class ToolSchema(BaseModel):
    """A tool description in the shape an OpenAI-compatible engine expects.

    Mirrors the ``function`` object of the OpenAI tools API. The tool layer
    produces these from its richer ``ToolSpec`` so the provider stays decoupled
    from the tool registry.
    """

    name: str
    description: str
    parameters: dict[str, object] = Field(default_factory=dict)  # JSON Schema


class ChatRequest(BaseModel):
    messages: list[Message]
    model: str
    tools: list[ToolSchema] = Field(default_factory=list)
    # GBNF grammar string; honored only when capabilities().supports_grammar.
    grammar: str | None = None
    temperature: float = 0.2
    max_tokens: int = 1024
    stop: list[str] = Field(default_factory=list)
    # When true and supported, ask the engine for parallel tool calls.
    parallel_tool_calls: bool = False


class ChatChunk(BaseModel):
    """One streamed increment from the engine."""

    delta_text: str | None = None
    # A *complete* tool call (we reassemble partials below the interface).
    tool_call: ToolCall | None = None
    finish_reason: str | None = None


class ProviderHealth(BaseModel):
    reachable: bool
    detail: str = ""
    models: list[str] = Field(default_factory=list)
    context_window: int | None = None


class ProviderCaps(BaseModel):
    supports_grammar: bool = False
    supports_native_tools: bool = True
    supports_parallel_tool_calls: bool = False


@runtime_checkable
class LLMProvider(Protocol):
    """The contract the agent loop relies on."""

    name: str

    def capabilities(self) -> ProviderCaps: ...

    async def health(self) -> ProviderHealth: ...

    def chat_stream(self, req: ChatRequest) -> AsyncIterator[ChatChunk]:
        """Stream the model's response to ``req``.

        Implementations are async generators; declared here as returning an
        ``AsyncIterator`` so the Protocol matches ``async def`` + ``yield``.
        """
        ...
