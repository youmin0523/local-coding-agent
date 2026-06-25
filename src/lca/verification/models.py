"""Value types for the verification gate."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

VerdictKind = Literal["pass", "fail", "uncertain"]


class JudgeVote(BaseModel):
    """One verifier's judgement of a candidate answer, from a specific lens."""

    lens: str
    passed: bool
    confidence: float = 0.5
    rationale: str = ""


class Verdict(BaseModel):
    """The gate's combined judgement — what decides deliver vs. abstain."""

    verdict: VerdictKind
    confidence: float
    rationale: str = ""
    signals: list[str] = []
