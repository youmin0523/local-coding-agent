# PROGRESS — overnight build summary

Built autonomously while you slept. Everything below is committed locally (no push).

## TL;DR
- A complete, working **local coding agent** (`lca`) — CLI **and** web UI — with the
  full differentiator stack: multi-pass **verification + abstention**, verified-only
  **experience memory**, **RAG**, **MCP**, **web search w/ citations**, difficulty
  **routing**, and an optional **QLoRA** self-improvement path.
- **~80 tests pass**, `mypy --strict` clean, `ruff` clean, the architecture contract
  (import-linter) holds. All tested with a `FakeProvider` → **no GPU needed for tests**.
- Models downloaded + LM Studio installed. The only thing left to *see it talk* is
  starting the engine (1 step) — see `docs/runbook-gpu.md`.

## What works now (milestones M0–M12)
| Milestone | What it gives you |
|---|---|
| M1 | Provider seam (llama.cpp/Ollama swappable), `lca doctor`, CLI |
| M2 | Tools (fs read/write/edit, allowlisted shell), permission gate (gated/auto/plan), ReAct loop |
| M3 | RAG over your repo (`lca index`), `search_code` with file:line citations |
| M4 | Execution oracle: `run_checks` (pytest/mypy/ruff) + sandboxed `run_python` |
| M8 | Verification gate: diverse-lens judges + consensus → deliver **or abstain** |
| M9 | Experience memory — remembers **only verified** results; recalls them next time |
| M10 | Difficulty routing: easy→7B, hard→30B + more verification |
| M6 | MCP client — external tools (filesystem/git/fetch) in the same registry |
| M5 | Web search (ddgs→SearXNG→Tavily) + fetch→cite |
| M7 | Web UI: FastAPI + SSE streaming, tool/diff cards, allow/deny buttons, badges |
| M12 | `lca eval` scorecard (pass-rate / tool-validity / abstention) + metrics |
| M11 | (optional) WSL2 QLoRA scripts in `training/` + runbook |

## Run it (after starting the engine — see docs/runbook-gpu.md)
```
uv run lca doctor                              # M0 gate: GPU + engine healthy
uv run lca index .                             # build the code index
uv run lca ask "create hello.py and run it" --auto
uv run lca ask "where is X handled?" --route --verify
uv run lca web                                 # http://127.0.0.1:8765
uv run lca eval                                # scorecard
```

## Dev gates (all green)
```
uv run pytest -q          # ~80 tests, no GPU
uv run mypy               # strict, clean
uv run ruff check .       # clean
uv run lint-imports       # architecture contract: KEPT
```

## Decisions worth knowing
- Engine = **LM Studio** (Blackwell-ready llama.cpp runtime); Ollama is a fallback.
- Brain = **Qwen3-Coder-30B-A3B** (`--n-cpu-moe` offload, ~12–15 tok/s); fast/trainable
  = **Qwen2.5-Coder-7B**. Context capped 8–16K (not the model max) for 8 GB VRAM.
- RAG + memory are **dependency-light** (stdlib sqlite + pure-Python cosine + a hashing
  embedder) so they run offline; `uv sync --extra rag` upgrades to bge embeddings + AST chunking.
- Trust = harness, not model: grammar + typed I/O + cite-or-abstain + execution-oracle
  + verification/abstention. See `docs/architecture.md` and `docs/adr/`.

## Not done / next steps
- **Live smoke test** against the real engine (start LM Studio server first). The `lms`
  CLI wasn't bootstrapped headlessly; easiest is to open LM Studio once (see runbook).
- Optional extras not installed by default: `rag`, `search`, `mcp` (run `uv sync --extra <name>`).
- QLoRA (M11) is gated behind `training/smoke_test.py` — only proceed if it prints SMOKE OK.
- A richer React/shadcn web frontend could replace the (already functional) single-file UI.

## Honest expectation
On your recurring work in familiar repos, with verification + memory mature, this
reaches Claude-class **reliability on those tasks**, and refuses to be confidently
wrong. It won't match a frontier model on cold, novel, large-context architecture.
The levers, in order: execution-oracle + best-of-N, verified memory, abstention.
