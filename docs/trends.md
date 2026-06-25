# Public-repo structure trends (mid-2026)

## FastAPI backends
- Two layouts dominate: **flat/layered** (`app/api/routes` + `app/core` + `models.py` + `crud.py`, kept thin) vs **domain/feature-driven** (`src/<domain>/{router,service,schemas,models,dependencies,exceptions}.py`). Rule of thumb: start flat, refactor to per-domain once past a handful of resources.
- "Thin router" consensus: handlers only orchestrate; SQL lives in a data-access layer; cross-resource logic lives in a service layer. Raw SQL/external calls in endpoints = anti-pattern.
- Data access has no single winner: flat CRUD functions, a **generic typed async CRUD** (FastCRUD), explicit injected repository classes, or full repositories + Unit-of-Work (clean-arch/DDD/CQRS) — chosen by domain complexity.
- ORM split: SQLModel (table=schema) for greenfield; **SQLAlchemy 2.0 typed `Mapped[]` with separate Pydantic v2 schemas** for complex domains. Async (`async_sessionmaker`/`AsyncSession` via `Depends`, asyncpg) is the assumed baseline.
- Config standardized on **pydantic-settings `SettingsConfigDict`** (env_file, env_prefix, `nested_delimiter='__'`); legacy inner `Config` class is out. `Depends` is the DI backbone and the test seam (`dependency_overrides`).
- Repos: [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template), [zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices), [benavlabs/FastAPI-boilerplate](https://github.com/benavlabs/FastAPI-boilerplate), [ivan-borovets/fastapi-clean-example](https://github.com/ivan-borovets/fastapi-clean-example)

## Python tooling & packaging
- **uv is the default** (now outpacing Poetry on PyPI): one `pyproject.toml` + committed `uv.lock` at root; `uv` replaces pip/pipenv/poetry/pyenv/pipx. Pin `requires-python` + `.python-version`.
- `pyproject.toml` is the single config file — `setup.py`, `setup.cfg`, `.flake8`, `mypy.ini`, `pytest.ini`, `requirements*.txt` get folded in or deleted.
- **PEP 735 `[dependency-groups]`** for dev/test/docs/lint deps; `[project.optional-dependencies]` (extras) reserved for genuine user-facing features shipped to PyPI.
- src-vs-flat is now use-case driven: **src/ for distributed libraries** (catches wheel-vs-local bugs), flat for apps/services (FastAPI, Pydantic themselves stay flat).
- **Ruff** consolidated lint+format+import-sort (use an explicit `select` ruleset). mypy/pyright remain the production type checker (plugin ecosystems); Astral's Rust **ty** (beta, 1.0 targeted 2026) is a greenfield pilot only. CI standardizes on `astral-sh/setup-uv` + `uv sync --locked` + a 3.12–3.14 matrix.
- Repos: [astral-sh/uv](https://github.com/astral-sh/uv), [pydantic/pydantic](https://github.com/pydantic/pydantic) (model `pyproject.toml`), [astral-sh/ty](https://github.com/astral-sh/ty), [astral-sh/setup-uv](https://github.com/astral-sh/setup-uv)

## React SPAs
- **Feature-folder beats layer-folder**: thin technical top level (`app/`, `components/`, `hooks/`, `lib/`, `stores/`, `utils/`) + `features/<name>/` repeating that shape internally. Layer-only is fine only for <~15-component apps.
- **Enforced unidirectional imports** (shared → features → app); no feature-to-feature imports; each feature exposes a single `index.ts` public API. Enforce mechanically (ESLint boundaries / steiger), not by convention.
- **Split state by source**: TanStack Query for server/async state (per-feature `api/` + hierarchical query-key factories), Zustand for client/UI state (thin global, feature-local stores), nuqs for URL state. Caching server data in a global store = anti-pattern.
- Zustand is the pragmatic default; Redux Toolkit for enforced patterns/large teams; Jotai for atomic reactivity. **Vite** is near-universal (`vite.config.ts`, `@/` alias mirrored in tsconfig, Vitest). React 19 **Actions / `useActionState` / `useOptimistic`** are the idiomatic mutation pattern (client-side in a plain SPA; RSC is meta-framework territory).
- Repos: [alan2207/bulletproof-react](https://github.com/alan2207/bulletproof-react), [feature-sliced/documentation](https://github.com/feature-sliced/documentation), [feature-sliced/steiger](https://github.com/feature-sliced/steiger), [TanStack/query](https://github.com/tanstack/query)

## LLM coding agents
- **Harness-over-model**: a thin, vendor-agnostic loop that drives any model; coupling pushed to one provider seam (LiteLLM-style over Ollama/vLLM for local).
- **Event-sourced state**: immutable Action/Observation event log + one mutable `ConversationState` → deterministic replay, pause/resume, audit, streaming.
- Tools as **`Action`(Pydantic v2) → Executor → `Observation`** triples, registered by name, JSON-serializable; designed *for* the model (ACI), not wrapped human CLIs. Prefer a small core (read/edit/run_shell/grep/glob) + a code-execution tool. **Code-execution + progressive tool disclosure** is the biggest 2026 context/cost lever (~98% reduction).
- **MCP** is the default external-tool boundary (auto-translate server JSON Schema → internal Action models). **Risk-tiered permissions** (SecurityAnalyzer LOW/MED/HIGH + ConfirmationPolicy + `WAITING_FOR_CONFIRMATION`) gate destructive actions; isolate in Docker/microVM (shared-kernel containers are not a sandbox). A **Condenser/summarizer** + sub-agent delegation keep context small; skills/config externalized as markdown/YAML.
- Repos: [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands), [huggingface/smolagents](https://github.com/huggingface/smolagents), [SWE-agent/SWE-agent](https://github.com/SWE-agent/SWE-agent), [BerriAI/litellm](https://github.com/BerriAI/litellm)

## RAG & evaluation
- **Chunking is a pluggable layer** (one class per strategy). Recursive ~512-token splitting is a strong default (beats naive semantic); use an **AST/structure-aware CodeChunker** for code. Enrich *before* embedding: contextual blurbs (Anthropic Contextual Retrieval, ~49–67% fewer failed retrievals) and late chunking beat overlap tuning.
- **Three-stage retrieval as explicit stages**: hybrid (BM25 + dense) → **RRF fusion** (rank-based, k=60) → cross-encoder/late-interaction rerank. Reranker behind a swappable interface yields most precision.
- **Vector store by deployment shape**, hidden behind a `VectorStore` Protocol: sqlite-vec/pgvector for local (vectors beside relational data), Chroma for prototyping, LanceDB for larger-than-RAM. Cores trend Rust/C + thin clients.
- **Evals-as-unit-tests** (DeepEval: typed test cases + thresholded metrics + pytest, as a CI gate) vs **offline experiment harness** (RAGAS, promptfoo YAML). Anchor on a committed golden dataset; score retrieval (Pass@k, context precision/recall) + generation (faithfulness, LLM-judge).
- Repos: [chonkie-inc/chonkie](https://github.com/chonkie-inc/chonkie), [AnswerDotAI/rerankers](https://github.com/AnswerDotAI/rerankers), [confident-ai/deepeval](https://github.com/confident-ai/deepeval), [explodinggradients/ragas](https://github.com/explodinggradients/ragas)

## What lca already does well / could adopt
- **Already aligned**: layered api/services/models/schemas maps ~1:1 onto `server/core(loop)/tools(executors)/providers`; Pydantic v2 schemas → tool `Action`/`Observation` contracts; uv+ruff+pytest+mypy is the right backbone; pytest is the verification signal (executable truth, not LLM-judge).
- **Adopt — loop**: make `ConversationState` event-sourced (append-only log + one mutable state) for replay/pause/resume; add a Condenser + bounded sub-agent delegation early.
- **Adopt — tools/providers**: register tools in a dict `ToolRegistry` (Action→Executor→Observation); put a LiteLLM-style seam targeting Ollama/vLLM with a non-native tool-calling shim; integrate MCP so native and external tools are indistinguishable; add risk-tiered confirmation + Docker/microVM workspace (it runs shell locally).
- **Adopt — RAG**: model a `RetrievalService` composing SparseRetriever/DenseRetriever/Fuser(RRF)/Reranker behind Protocols; use pgvector (already on Postgres/asyncpg) + an AST CodeChunker + contextual enrichment.
- **Adopt — verification**: build the eval stage as DeepEval-style evals-as-unit-tests over a committed golden set, gated in CI; reserve RAGAS for offline chunking/embedding sweeps. Ingest these repos as the agent's "gold" RAG/learning corpus.
- **Adopt — frontend**: mirror backend boundary discipline with bulletproof-react feature-folders + enforced shared→features→app; pair Zustand with TanStack Query (don't store server data in Zustand); wrap the agent core as SDK + CLI + IDE-extension + WebSocket server.
