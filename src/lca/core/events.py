"""The agent's streaming event protocol.

`Agent.run_turn` is an async generator of `AgentEvent`s. The CLI renders them with
Rich; the web backend serializes them to SSE. Because both UIs consume this exact
union and nothing else, the core stays genuinely UI-agnostic — this is the single
seam that makes "one core, two front-ends" real.

Every event is a JSON-serializable Pydantic model discriminated on ``type``.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from lca.core.messages import ToolCall
from lca.tools.base import RiskLevel, ToolResult


class TokenDelta(BaseModel):
    type: Literal["token"] = "token"
    text: str


class ToolProposed(BaseModel):
    type: Literal["tool_proposed"] = "tool_proposed"
    call: ToolCall
    risk: RiskLevel


class ApprovalRequired(BaseModel):
    type: Literal["approval_required"] = "approval_required"
    request_id: str
    call: ToolCall
    risk: RiskLevel
    preview: str = ""  # human-readable diff/command preview of the pending change


class ApprovalResolved(BaseModel):
    type: Literal["approval_resolved"] = "approval_resolved"
    request_id: str
    approved: bool


class ToolStarted(BaseModel):
    type: Literal["tool_started"] = "tool_started"
    call_id: str
    name: str


class ToolFinished(BaseModel):
    type: Literal["tool_finished"] = "tool_finished"
    call_id: str
    name: str
    result: ToolResult


class VerificationResult(BaseModel):
    type: Literal["verification"] = "verification"
    verdict: str  # "pass" | "fail" | "uncertain"
    confidence: float
    detail: str = ""


class Abstained(BaseModel):
    type: Literal["abstain"] = "abstain"
    reason: str
    options: list[str] = Field(default_factory=list)


class ContextRecalled(BaseModel):
    """Emitted once at the start of a turn when prior context informs the answer.

    Surfaces two otherwise-invisible differentiators: ``experiences`` = verified
    past solutions reused from the experience memory (self-improvement), and
    ``snippets`` = repository chunks pulled in by RAG (grounding). Lets the UI
    show *why* an answer is trustworthy, not just the answer.
    """

    type: Literal["context_recalled"] = "context_recalled"
    experiences: int = 0
    snippets: int = 0
    detail: str = ""


class ReflectionNote(BaseModel):
    type: Literal["reflection"] = "reflection"
    text: str


class TurnFinished(BaseModel):
    type: Literal["turn_finished"] = "turn_finished"
    stop_reason: str  # "complete" | "abstained" | "budget" | "error"
    content: str = ""


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str
    recoverable: bool = False


AgentEvent = Annotated[
    TokenDelta
    | ToolProposed
    | ApprovalRequired
    | ApprovalResolved
    | ToolStarted
    | ToolFinished
    | VerificationResult
    | Abstained
    | ContextRecalled
    | ReflectionNote
    | TurnFinished
    | ErrorEvent,
    Field(discriminator="type"),
]
