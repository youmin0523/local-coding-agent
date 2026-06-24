"""Provider-neutral conversation types.

These are the canonical shapes the agent works in; each provider adapter maps
them to/from its wire format (OpenAI chat, Anthropic messages, …). Keeping them
independent of any SDK is what lets us swap llama.cpp for Ollama without touching
the agent loop.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]


class ToolCall(BaseModel):
    """A model-requested tool invocation.

    ``arguments`` is always a parsed dict here. The wire layer is responsible for
    normalizing engines that emit the arguments as a JSON *string* vs a JSON
    *object* (llama.cpp issue #20198) before constructing this object.
    """

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    """One turn in the conversation."""

    role: Role
    content: str | None = None
    # Present on assistant messages that request tools.
    tool_calls: list[ToolCall] = Field(default_factory=list)
    # Present on role="tool" messages, linking a result to its ToolCall.id.
    tool_call_id: str | None = None
    # Optional display name for tool results.
    name: str | None = None

    @classmethod
    def system(cls, content: str) -> Message:
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> Message:
        return cls(role="user", content=content)

    @classmethod
    def assistant(
        cls, content: str | None = None, tool_calls: list[ToolCall] | None = None
    ) -> Message:
        return cls(role="assistant", content=content, tool_calls=tool_calls or [])

    @classmethod
    def tool_result(cls, tool_call_id: str, content: str, name: str | None = None) -> Message:
        return cls(role="tool", content=content, tool_call_id=tool_call_id, name=name)
