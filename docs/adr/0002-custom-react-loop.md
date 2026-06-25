# ADR 0002 — Hand-written ReAct loop over a heavy framework

## Status
Accepted.

## Context
Portfolio goal: demonstrate real engineering, not framework glue. But reliability
with a small local model still matters.

## Decision
Write the ReAct loop, tool dispatch, permission gate, and event stream **ourselves**
(`lca.core`). Use libraries only for plumbing: httpx (engine), sqlite (RAG/memory),
the MCP SDK, embeddings. Pydantic provides typed/validated tool I/O. We do **not**
adopt a full agent framework (LangGraph/OpenHands) or a framework's runner.

## Consequences
- The loop is the readable centerpiece; `FakeProvider` makes all of it deterministically
  testable with zero GPU (77 tests, no engine needed).
- We own behavior (streaming, abstention, budgets) instead of fighting a framework.
- More code to maintain — mitigated by strict typing, tests, and the layer contract.
