# lca — Local Coding Agent

A **100% local, free, privacy-preserving** coding agent that runs entirely on your
own hardware — no code ever leaves the machine. Built to do the things you'd ask a
cloud assistant to do while coding (write scripts, summarize logs, search the web,
read and edit code across a real repository) while being **verification-grounded**:
answers pass a multi-pass verification gate before they reach you, and the agent
**abstains** rather than guess when it isn't sure.

> Designed for the case where company policy forbids external AI: the model, the
> retrieval index, the memory, and even the optional fine-tuning all stay on-device.

## Why it can be trusted

It does not rely on the model being right. It relies on a harness that checks the
model:

1. **GBNF grammar-constrained tool calls** — malformed tool calls are structurally impossible.
2. **Typed, validated tool I/O** (Pydantic) with self-repair on bad arguments.
3. **Cite-or-abstain** for web answers.
4. **Execution as the oracle** — it runs tests / type-checkers / linters and treats
   their output as ground truth, not its own beliefs.
5. **Multi-pass verification + calibrated abstention** — best-of-N candidates are
   selected by execution behavior; diverse-lens judges confirm; low-confidence
   answers are withheld.

And it **improves over time**: every execution-verified result is remembered (a
local ReasoningBank-style experience memory), and — optionally — used to fine-tune
the 7B model.

## What it can do

- **Write / edit / run code** across a real repo (RAG-indexed, cited by `file:line`).
- **Summarize logs** and **debug from a traceback**, grounded in the actual lines.
- **Search the web** and answer with citations (or abstain).
- **Open a real browser** (Playwright) to screenshot a page and run E2E smoke
  checks — `browser_screenshot`, `browser_check`.
- **Block secret leaks** — `secret_scan` flags hardcoded API keys/tokens/passwords
  and audits `.gitignore` (secrets belong in env, not in code).
- **Apply any tech** via a local, cited **reference knowledge base** (`reference_docs`):
  ~150 cards spanning languages, frameworks, libraries, deployment, error→fix
  recipes, OWASP security, and UI/UX design — backed by `docs/`.
- **Generate office documents** — Word (`.docx`), PowerPoint (`.pptx`), and Excel
  (`.xlsx`) via bundled skills (python-docx / python-pptx / openpyxl).
- **Agent Skills** — loads Claude-compatible `SKILL.md` files (progressive
  disclosure + a `use_skill` tool); ships skills for normalized schemas, secure
  endpoints, accessible components, log triage, debugging, deployment, and
  document/slide/spreadsheet generation.
- **MCP** client (filesystem/git/fetch) — native + MCP tools in one registry.

## Hardware target

NVIDIA RTX 5070 Laptop (Blackwell, 8 GB VRAM) · Ryzen 9 · 32 GB RAM · Windows 11.
The "brain" is **Qwen3-Coder-30B-A3B** (MoE) via llama.cpp `--n-cpu-moe` offload;
the fast/fine-tunable model is **Qwen2.5-Coder-7B-Instruct**. Engine: **LM Studio**
(bundled CUDA-12.8 llama.cpp runtime), with Ollama as a swappable fallback.

## Quickstart

```bash
uv sync                     # install (Python 3.12+, uv); extras: rag,search,mcp,web,browser
uv run lca doctor           # verify GPU + engine are healthy (run this FIRST)
uv run lca index .          # build the code index (RAG)
uv run lca ask "create hello.py and run it" --auto   # smart-by-default (auto-routes)
uv run lca chat             # interactive multi-turn session
uv run lca web              # browser UI at http://127.0.0.1:8765
uv run lca skills           # list the Agent Skills (SKILL.md) available to the agent
uv run lca mcp              # connect + list local MCP tools (filesystem/git/fetch)
uv run lca learn            # RLVR self-improvement: rollout -> reward -> SFT dataset
uv run lca stats            # how much it has learned/indexed

# browser tools (optional): install Playwright + a browser once
uv sync --extra browser && uv run playwright install chromium
```

## How it learns (RL / DL, on-device)

```
rollout (run tasks)  →  reward (execution/verification pass)  →  keep verified only
   →  remember (in-context, no training)  →  export SFT corpus  →  QLoRA gradient step (WSL2)
```

`lca learn` runs the first steps locally (rejection sampling with a verifiable reward —
STaR/RLVR); the experience **memory** is the no-train half (only verified results are
written); the optional QLoRA stage (`training/`, WSL2) is the gradient-descent half.
Watch progress with `lca stats`.

`lca doctor` is the M0 gate: it confirms a discrete NVIDIA GPU is active and the
engine endpoint is reachable before anything is built on top. See
[`docs/runbook-gpu.md`](docs/runbook-gpu.md) for installing LM Studio and the models.

**See it run — [`docs/demo.md`](docs/demo.md)** (captured web + CLI walkthrough).
**Full walkthrough — [`docs/usage.md`](docs/usage.md).** Note: lca defaults to the
engine on `:8080`; LM Studio serves `:1234`, so set
`LCA_LLM__BASE_URL=http://127.0.0.1:1234/v1` (and `LCA_PROFILE=quality` for the 30B).

## Architecture (layers)

```
cli / web            UI adapters (Typer+Rich, FastAPI+SSE)
  └─ core            UI-agnostic agent: ReAct loop, session, event stream
       └─ providers, tools, rag, memory, verification, routing, mcp,
          permissions, skills, references
            └─ config, observability
```

Nothing below `core` may import `cli`/`web` (enforced by import-linter). That is what
lets the terminal and the browser consume the exact same agent.

See the full plan and milestones in
[`docs/architecture.md`](docs/architecture.md) and `docs/PROGRESS.md`.

## Development

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest                 # fast suite (mocks + FakeProvider, no GPU)
uv run pytest -m live         # opt-in: requires a running engine
uv run lint-imports           # architecture contract
```

## License

MIT.
