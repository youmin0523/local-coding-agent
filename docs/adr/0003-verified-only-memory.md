# ADR 0003 — Memory writes only verified experiences

## Status
Accepted.

## Context
Agent memory that learns from its own runs can be *poisoned*: a hallucinated
"success" gets remembered and misleads future turns (MINJA/MemoryGraft-style).

## Decision
The experience memory's **write path is the verification gate**: `remember()` only
persists a task→answer when it was execution-verified / judged `pass`. Recall is kept
small (k≤2) — more retrieved memory measurably hurts.

## Consequences
- Self-poisoning is structurally impossible: unverified outcomes never enter the store.
- Memory compounds value on the user's recurring workload at zero training cost/risk.
- It is also the corpus for the optional QLoRA (RFT) — no separate data pipeline.
