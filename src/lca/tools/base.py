"""The Tool contract.

Every capability the agent has — reading files, editing, running a command,
searching code, fetching the web, an MCP tool — implements `Tool`. The contract
is deliberately small:

* a static `ToolSpec` (name, description, a *flat* JSON-Schema for arguments, and
  a `RiskLevel`) that drives both the model's tool list and the GBNF grammar;
* an async `run(args, ctx)` returning a `ToolResult`.

`RiskLevel` is declared, not inferred, so the permission layer is auditable.
`ToolResult.is_truth` marks results that come from execution (tests/linters) —
the verification layer treats those as ground truth rather than model belief.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # avoid import cycles; these are only type hints on ToolContext
    from lca.core.session import Session
    from lca.permissions.approver import Approver
    from lca.permissions.sandbox import SandboxRunner


class RiskLevel(IntEnum):
    """How dangerous a tool is. READ is always free; the rest are gated by default."""

    READ = 0
    WRITE = 1
    SHELL = 2
    NETWORK = 3


class ToolSpec(BaseModel):
    """Static description of a tool, in a shape usable by the engine and grammar."""

    name: str
    description: str
    # JSON Schema for the arguments object. Keep it FLAT (avoid deep nesting) so
    # llama.cpp's GBNF conversion stays robust (#1484).
    parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
    risk: RiskLevel = RiskLevel.READ


class Artifact(BaseModel):
    """A structured side-output of a tool (a diff, a file reference, a citation)."""

    kind: str  # "diff" | "file" | "citation" | "output"
    title: str = ""
    body: str = ""
    uri: str = ""


class ToolResult(BaseModel):
    """What a tool returns. ``content`` is the text fed back to the model."""

    ok: bool = True
    content: str = ""
    artifacts: list[Artifact] = Field(default_factory=list)
    # True when this result is an un-fabricatable signal (test/lint/type output).
    is_truth: bool = False

    @classmethod
    def ok_text(cls, content: str, **kw: Any) -> ToolResult:
        return cls(ok=True, content=content, **kw)

    @classmethod
    def error(cls, content: str, **kw: Any) -> ToolResult:
        return cls(ok=False, content=content, **kw)


@dataclass
class ToolContext:
    """Runtime context injected into every tool call (never model-controlled)."""

    workspace_root: Path
    approver: Approver
    session: Session
    sandbox: SandboxRunner | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Tool(Protocol):
    spec: ToolSpec

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult: ...
