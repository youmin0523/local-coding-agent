"""A tiny in-process metrics collector.

Counters (tool calls, failures, abstentions, turns) and value series (tok/s,
latency) with a snapshot for reporting. Deliberately dependency-free; an
OpenTelemetry exporter can be layered on later.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel


class MetricsSnapshot(BaseModel):
    counters: dict[str, int]
    means: dict[str, float]


class Metrics:
    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._values: dict[str, list[float]] = defaultdict(list)

    def incr(self, name: str, n: int = 1) -> None:
        self._counters[name] += n

    def observe(self, name: str, value: float) -> None:
        self._values[name].append(value)

    def snapshot(self) -> MetricsSnapshot:
        means = {k: sum(v) / len(v) for k, v in self._values.items() if v}
        return MetricsSnapshot(counters=dict(self._counters), means=means)
