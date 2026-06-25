"""Eval task + scorecard types."""

from __future__ import annotations

from pydantic import BaseModel


class EvalTask(BaseModel):
    id: str
    prompt: str
    must_contain: list[str] = []
    expect_abstain: bool = False


class TaskResult(BaseModel):
    id: str
    passed: bool
    abstained: bool
    tool_calls: int
    tool_failures: int
    detail: str = ""


class Scorecard(BaseModel):
    total: int
    passed: int
    tool_calls: int
    tool_failures: int
    results: list[TaskResult]

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def tool_validity(self) -> float:
        if self.tool_calls == 0:
            return 1.0
        return 1.0 - self.tool_failures / self.tool_calls
