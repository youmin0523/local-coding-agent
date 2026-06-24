"""Typed error hierarchy for lca.

A small, explicit hierarchy keeps failure handling legible: the agent loop can
distinguish "the engine is unreachable" from "the model emitted an unparseable
tool call" from "the user denied a tool" without string-matching.
"""

from __future__ import annotations


class LcaError(Exception):
    """Base class for all lca errors."""


class ProviderError(LcaError):
    """The inference engine failed or returned something unusable."""


class EngineUnavailableError(ProviderError):
    """The llama-server / engine endpoint could not be reached."""


class ToolError(LcaError):
    """A tool failed in a way the agent should observe and react to."""


class ToolNotFoundError(ToolError):
    """The model requested a tool that is not in the registry."""


class PermissionDeniedError(LcaError):
    """The user (or policy) denied a tool invocation."""


class SandboxError(LcaError):
    """Sandboxed execution failed to set up or was killed by a guard."""


class BudgetExceededError(LcaError):
    """A turn hit a hard cap (tool iterations, wall-clock, or token budget)."""
