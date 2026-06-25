# Architecture

`lca` is a local, verification-grounded coding agent. The design goal is that
**trust comes from the harness, not the model**: a small local model is wrapped in
layers that ground, check, and (when unsure) refuse.

## Layers (enforced by import-linter)

```
cli / web                UI adapters (Typer+Rich · FastAPI+SSE)
   │  build via
assembly                 composition root (wires a fully-configured Agent)
   │
core                     ReAct loop, Session, the AgentEvent stream, messages
   │
providers · tools · rag · memory · verification · routing · mcp · permissions
   │
config · observability   settings, paths, structured logging, metrics
```

Nothing at or below `core` may import `cli`/`web` (a CI contract). That is what lets
the terminal and the browser run the **same** agent.

## The turn (ReAct loop)

`Agent.run_turn(session, input)` is an async generator of `AgentEvent`s:

1. **Retrieve** — code chunks (RAG) + verified experiences (memory, k≤2).
2. **Build context** — system prompt (ground/cite/abstain rules) + tools + retrieved.
3. **Call model (stream)** — tokens stream out live; tool calls are parsed.
4. **Permission gate** — READ free; WRITE/SHELL/NETWORK → allow/deny/ask by mode.
5. **Execute in sandbox** — observations fed back; loop until no tool call.
6. **Verify (optional)** — diverse-lens judges + execution → `pass` delivers,
   else **abstain**.
7. **Remember (on pass)** — write the verified experience for next time.

## Anti-hallucination (defense in depth)

1. GBNF grammar (structurally valid tool calls / verdicts).
2. Typed tool I/O + self-repair on bad arguments.
3. Cite-or-abstain for web claims (search → fetch → cite).
4. **Execution as oracle** — tests/types/lint override belief (`is_truth`).
5. Multi-pass verification + **calibrated abstention** (refuse rather than guess).

## Self-improvement loop

The single `verify()` green/red bit does triple duty: it gates what reaches the
user, gates what is **remembered** (only verified experiences are written —
the anti-poisoning rule), and labels what could later be **trained on** (optional
WSL2 QLoRA of the 7B, fed by the same memory). "Only correct things get remembered;
only remembered-correct things get trained on."

## Key swap points (interfaces)

- `LLMProvider` — llama.cpp ↔ Ollama ↔ FakeProvider (tests).
- `Tool` / `ToolRegistry` — native + MCP tools, one homogeneous list.
- `VectorStore` / `Retriever` / `Embedder` — sqlite today, ANN later.
- `Approver` — CLI prompt ↔ web HTTP callback.
- `Verifier` / `Memory` — opt-in, faked in tests.
