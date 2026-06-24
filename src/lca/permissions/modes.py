"""Autonomy modes and the risk ceiling.

* ``GATED`` (default) — READ is free; WRITE/SHELL/NETWORK require approval.
* ``AUTONOMOUS`` — auto-approve everything up to a configurable *risk ceiling*
  (default: SHELL, so file edits and commands run unattended but network calls
  still ask). Opt-in per run.
* ``PLAN`` — never execute side effects; the agent only *proposes* actions.
"""

from __future__ import annotations

from enum import StrEnum

from lca.tools.base import RiskLevel


class AutonomyMode(StrEnum):
    GATED = "gated"
    AUTONOMOUS = "autonomous"
    PLAN = "plan"

    @classmethod
    def parse(cls, value: str) -> AutonomyMode:
        return cls(value)


# In AUTONOMOUS mode, calls at or below this risk are auto-approved.
DEFAULT_RISK_CEILING = RiskLevel.SHELL
