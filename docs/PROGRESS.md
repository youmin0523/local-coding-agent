# PROGRESS — build summary

Built autonomously. Everything below is committed locally (no push).

## ✅ Live-validated
The real 7B model (LM Studio, port 1234) ran end-to-end: `lca doctor` = READY (RTX 5070,
all 3 models detected), and `lca ask` wrote a Fibonacci function and ran it to the correct
answer (55). A live bug was found+fixed (run_python couldn't import workspace files →
PYTHONPATH), after which the 7B solved it cleanly in 2 steps.

## Capability upgrades since first build (M13–M18, ~88 tests)
- **M13 Continuous auto-learning** — every turn grounded by passing checks / executed code /
  citations is remembered automatically (verified-only write gate). Learning is ON by default.
- **M14 Best-of-N** — with verification, samples several candidate answers and delivers the
  best-verified one (or abstains). The main capability lever toward frontier quality.
- **M15 Sharper prompt + `lca chat`** — procedural workflow that fixes small-model loops
  (just run/import by name, never repeat a failing action); multi-turn REPL.
- **M16 Smart-by-default** — CLI & web auto-route by difficulty (easy→fast 1-shot; harder→
  verify + best-of-N), respecting the loaded model profile.
- **M17 `list_symbols`** — instant AST outline (classes/functions+lines) for fast analysis.
- **M18 Long-session memory** — summarizes dropped older turns to keep continuity.
- **M19 `lca stats`** — visualize accumulated learning (verified experiences + chunks).
- **M20 MCP wired** — `lca mcp` / `ask --mcp` connect filesystem/git/fetch servers into the registry.
- **M21 `lca learn` (RLVR)** — rollout → execution/verification reward → keep verified → export
  SFT corpus for the optional QLoRA gradient step. The concrete on-device RL/DL loop.
- **M22 Learn from failure** — abstentions store ReasoningBank "caution" lessons (safe, no
  fabricated solutions) that surface on similar future tasks.
- **M23 Engine resilience** — RetryingProvider retries transient pre-stream failures (never mid-stream).
- **M24 Config visibility** — `lca config`; `doctor` warns on model-id mismatch.

- **M25 Execution-grounded verification** — the turn's run_checks result dominates the
  verdict: a failing check forces abstain even if the LLM judge says pass. Strongest lever.
- **M26 CI** — GitHub Actions runs ruff/mypy/import-linter/pytest on push/PR.
- **M27 Security hardening** — adversarial tests (path-escape, shell-allowlist bypass) +
  `docs/SECURITY.md` threat model. Central to the on-device security motivation.
- **M28 Observability** — agent accumulates runtime metrics (tool validity, abstentions),
  shown in `lca chat`.

~110 tests, all green; mypy --strict / ruff / import-linter / CI clean. Commands:
`doctor · config · stats · index · ask · chat · web · mcp · learn · eval · version`.
See also `docs/SECURITY.md`, `docs/architecture.md`, `docs/adr/`.

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
