## Developer Stack & Conventions

**Backend (Python):** FastAPI + Pydantic v2 + SQLAlchemy 2.0 async (asyncpg) + Alembic on PostgreSQL 16. Layered architecture: `api/` routers delegate to `services/`, which use `models/` (ORM) and `schemas/` (Pydantic). JWT + bcrypt auth via `Depends(get_current_user)`. EventBus/async workers for long jobs. Tests with pytest + pytest-asyncio (`asyncio_mode=auto`), AsyncMock + `dependency_overrides`.

**Backend (Node):** Express + Socket.io + PostgreSQL with CommonJS modules; parameterized queries (`$1, $2`); error-first try-catch returning `{status, message, data}`; socket handlers as `(io, socket, state) => {}`.

**Frontend:** React 18/19 + Vite; Zustand state (selector helpers to limit rerenders); Tailwind CSS; Framer Motion / GSAP (respect `prefers-reduced-motion`); axios instances auto-injecting JWT from sessionStorage. TypeScript only in fde-portfolio; otherwise JSX + JSDoc.

**Naming:** Python `snake_case` functions/vars, `PascalCase` classes, `SCREAMING_SNAKE_CASE` constants. JS `camelCase` functions/handlers, `PascalCase` `.jsx` component files. Full type hints / `from __future__ import annotations`.

**Style:** Bilingual Korean+English docstring headers at file/function head (domain terms preserved, e.g. `open_w`, `maguri`). Ruff (line-length 100, py311). Pydantic `Field` constraints + `computed_field`; `Protocol` for polymorphism; enums/`Literal` for status.

**Error handling:** `HTTPException(status_code=4xx)` at API layer, `ValueError` for domain logic; graceful optional-dependency fallbacks. Config via pydantic-settings/`.env` with placeholder-secret detection. Seeded PRNG for deterministic sims; JSONL event sourcing for replay/audit.
