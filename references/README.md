# Reference catalog index

127 cards across 13 categories — surfaced by the reference_docs tool (with fetch_url for live detail).

## db
- [PostgreSQL](https://www.postgresql.org/docs/current/) — Use PostgreSQL as a general-purpose, ACID-compliant relational database when you need stro

## deployment
- [Alembic](https://alembic.sqlalchemy.org/en/latest/) — Schema migrations for SQLAlchemy/PostgreSQL across deploys.
- [Caddy](https://caddyserver.com/docs/) — Reverse proxy + automatic HTTPS for an API+SPA with minimal config.
- [Cloudflare Pages](https://developers.cloudflare.com/pages/) — Free, fast global hosting for the static SPA.
- [Docker Compose](https://docs.docker.com/compose/) — Local dev and small single-host deploys of multi-container apps (api+db+redis).
- [Fly.io](https://fly.io/docs/) — Deploy a Dockerized FastAPI + Postgres close to users with one CLI.
- [GitHub Actions](https://docs.github.com/actions) — CI/CD: test on PR, build+deploy on merge.
- [gunicorn](https://docs.gunicorn.org/en/stable/) — Production process manager for ASGI/WSGI Python apps with multiple workers.
- [nginx](https://nginx.org/en/docs/) — Battle-tested static server + reverse proxy (manual TLS).
- [Railway](https://docs.railway.com/) — Fastest PaaS for an API + managed database from a repo.
- [Render](https://render.com/docs) — PaaS for API + DB + static site with infra-as-code.
- [uvicorn](https://www.uvicorn.org/) — ASGI server for FastAPI/Starlette in dev and prod.
- [Vercel](https://vercel.com/docs) — Deploy the static SPA with CDN + preview deploys.

## design
- [Accessible forms](https://www.w3.org/WAI/tutorials/forms/ ; aria-invalid: https://www.w3.org/WAI/WCAG21/Techniques/aria/ARIA21) — Any form, login, search box, or single input field.
- [Alignment & proximity (Gestalt)](https://www.interaction-design.org/literature/topics/gestalt-principles) — Laying out cards, forms, lists, and any grouped content. Fixes 'looks broken / messy' inte
- [Ant Design](https://ant.design/docs/react/migration-v6/) — Choose for data-heavy enterprise/admin apps (tables, forms, dashboards) where a complete, 
- [Chakra UI](https://chakra-ui.com/docs/get-started/frameworks/vite) — Choose when you want a themeable, batteries-included system with very ergonomic DX (style 
- [cn() — clsx + tailwind-merge composition](https://github.com/dcastil/tailwind-merge) — Any reusable React component that exposes a className prop or builds class lists condition
- [Color system & 60-30-10 (Tailwind v4 @theme / OKLCH)](https://tailwindcss.com/blog/tailwindcss-v4) — Defining the design palette and applying color across the app. Add color after grayscale h
- [Consistency (tokens + reusable components)](https://tailwindcss.com/docs/theme) — As soon as a pattern repeats twice. Prevents drift and keeps the UI feeling unified.
- [Contrast (WCAG 2.2 AA/AAA)](https://www.w3.org/TR/WCAG22/) — Every color pairing of text, icons, and interactive controls. Non-negotiable for accessibi
- [Design principle — avoid class soup](https://tailwindcss.com/docs/styling-with-utility-classes) — Whenever a utility list grows long or repeats across elements/components.
- [Empty, loading & error states](https://tailwindcss.com/docs/animation) — Any async data view, list, table, or form submission.
- [Headless UI](https://headlessui.com/) — Choose for a pure-Tailwind project needing a handful of accessible interactive primitives 
- [Keyboard navigation & focus management](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/ ; Dialog pattern: https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) — Always — keyboard operability and logical focus order are AA requirements (2.1.1, 2.4.3, 2
- [Material UI (MUI)](https://mui.com/material-ui/getting-started/installation/) — Choose when you need a complete, consistent Material Design UI fast (enterprise dashboards
- [Motion (motion / Framer Motion) with reduced-motion](https://motion.dev/docs/react) — Transitions, enter/exit, hover/press feedback, and attention cues — sparingly and accessib
- [Motion for React — motion components & variants](https://motion.dev/docs/react) — Declarative React animations: entrance/exit, hover/tap gestures, staggered lists, scroll r
- [Motion — accessibility (prefers-reduced-motion)](https://motion.dev/docs/react-accessibility) — Always — wrap the app in MotionConfig reducedMotion='user' and branch heavy effects with u
- [Motion — AnimatePresence (exit animations)](https://motion.dev/docs/react-animate-presence) — Animating modals, toasts, route transitions, and list item removals where elements leave t
- [Motion — layout & shared-element animations](https://motion.dev/docs/react-layout-animations) — Reorderable lists, expanding cards, tab indicators, and shared-element transitions between
- [prefers-reduced-motion (Tailwind + Motion/GSAP)](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion ; Tailwind states: https://tailwindcss.com/docs/hover-focus-and-other-states) — Any time you add Framer Motion / GSAP / CSS animation beyond trivial micro-transitions.
- [Radix UI Primitives](https://www.radix-ui.com/primitives/docs/overview/getting-started) — Choose when building a bespoke/custom design system and you want complete visual control w
- [Responsive breakpoints (Tailwind v4, mobile-first)](https://tailwindcss.com/docs/responsive-design) — All layout that must adapt across devices.
- [Semantic HTML + ARIA (Using ARIA + APG)](https://www.w3.org/TR/using-aria/ ; APG: https://www.w3.org/WAI/ARIA/apg/ ; Patterns: https://www.w3.org/WAI/ARIA/apg/patterns/) — Reach for ARIA only when native HTML cannot express the role, state, or relationship you n
- [shadcn/ui](https://ui.shadcn.com/docs/installation/vite) — Default modern choice for React 19 + Vite + Tailwind. Pick when you want pre-styled, acces
- [Spacing & the 8pt grid (Tailwind v4 spacing scale)](https://tailwindcss.com/docs/padding) — All layout, padding, margins, and gaps. Enforces consistent vertical rhythm and clean hand
- [Tailwind CSS v4 — @theme design tokens](https://tailwindcss.com/docs/theme) — Defining a project's color/spacing/typography/radius/shadow design system in Tailwind v4 s
- [Tailwind Plus / Catalyst](https://catalyst.tailwindui.com/docs) — Choose when you/your org have a Tailwind Plus license and want a beautiful, production-rea
- [Tailwind — dark mode (@custom-variant)](https://tailwindcss.com/docs/dark-mode) — Adding light/dark theming, especially when you need a user-controlled toggle rather than p
- [Tailwind — responsive (mobile-first) + container queries](https://tailwindcss.com/docs/responsive-design) — Layouts that adapt to viewport (responsive) or to a component's own container width (conta
- [Typographic scale](https://tailwindcss.com/docs/font-size) — All text. Pick sizes from the scale only — avoid arbitrary text-[17px].
- [Visible focus & color contrast (Tailwind)](1.4.3: https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html ; Tailwind outline: https://tailwindcss.com/docs/outline-style ; WebAIM: https://webaim.org/articles/contrast/) — On every interactive element (focus) and every text/UI color pair (contrast).
- [Visual hierarchy (size / weight / color)](https://www.interaction-design.org/literature/topics/visual-hierarchy) — Every screen. The first thing to get right before color, decoration, or motion.
- [WCAG 2.2 (Level AA)](https://www.w3.org/TR/WCAG22/ ; What's new: https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/) — The baseline conformance standard for every production web UI; gate releases on AA.
- [Whitespace](https://www.designsystems.com/space-grids-and-layouts/) — Layout composition, especially hero/landing and content-heavy pages.

## frontend
- [React 19](https://react.dev/) — Use React 19 to build interactive UIs and full-stack web/native apps when you want first-c
- [React Hooks](https://react.dev/reference/react/hooks) — State, side effects, and reusable stateful logic in React function components.
- [Tailwind CSS](https://tailwindcss.com/docs) — Use Tailwind CSS when you want to build and maintain custom UI rapidly by composing utilit
- [Zustand](https://zustand.docs.pmnd.rs/) — When you need a lightweight, hook-based, boilerplate-free global state store for React (no

## infra
- [Docker](https://docs.docker.com/) — Use Docker to package an application and its dependencies into portable, reproducible cont

## language
- [Node.js](https://nodejs.org/api/index.html) — Use Node.js to run JavaScript/TypeScript outside the browser for servers, APIs, CLIs, buil
- [Python (3.12+)](https://docs.python.org/3/) — A high-level, general-purpose, dynamically typed language ideal for scripting, automation,
- [TypeScript](https://www.typescriptlang.org/docs/) — Use TypeScript when you want static type checking, richer editor tooling, and safer refact

## library
- [@tanstack/react-query](https://tanstack.com/query/latest/docs/framework/react/overview) — Use it to manage server state: fetching, caching, background refetching, pagination, and i
- [aiohttp](https://docs.aiohttp.org/en/stable/) — Choose aiohttp for fully asynchronous, high-concurrency HTTP clients and when you want a m
- [asyncpg](https://magicstack.github.io/asyncpg/current/) — Choose asyncpg for high-performance asyncio access directly to PostgreSQL; it is significa
- [axios](https://axios.rest/) — Choose axios when you want batteries-included HTTP: automatic JSON parse/stringify, interc
- [celery](https://docs.celeryq.dev/en/stable/) — Choose Celery for a mature, full-featured distributed task queue: scheduled jobs, retries,
- [click](https://click.palletsprojects.com/) — Choose Click when you want a mature, explicit, composable decorator-based CLI toolkit with
- [clsx](https://github.com/lukeed/clsx) — Use clsx to conditionally build className strings; it's a tiny (~240B), faster, drop-in re
- [date-fns](https://date-fns.org/docs/Getting-Started) — Use date-fns for a lightweight, tree-shakeable, immutable, function-based date toolkit whe
- [drizzle-orm](https://orm.drizzle.team/docs/get-started) — Choose Drizzle for TypeScript-first projects wanting a thin (~7kb, zero-dependency), tree-
- [eslint](https://eslint.org/docs/latest/use/getting-started) — Choose ESLint to catch bugs and enforce code-quality/correctness rules across JS/TS (unuse
- [fastembed](https://qdrant.github.io/fastembed/) — Choose FastEmbed when you need fast, lightweight local embedding generation without pullin
- [framer-motion](https://motion.dev/docs/react) — Choose this for declarative, gesture- and layout-aware animations in React. NOTE: as of mi
- [httpx](https://www.python-httpx.org/) — Choose httpx when you need a single HTTP client API that works in both sync and async code
- [hypothesis](https://hypothesis.readthedocs.io/) — Choose Hypothesis for property-based testing when you want to assert invariants over a wid
- [matplotlib](https://matplotlib.org/stable/) — The foundational, highly customizable Python plotting library for static figures and publi
- [numpy](https://numpy.org/doc/stable/) — Foundational n-dimensional array and numerical computing layer for almost all Python scien
- [onnxruntime](https://onnxruntime.ai/docs/) — Use ONNX Runtime for fast, portable inference of trained models exported to ONNX, across C
- [opencv-python](https://docs.opencv.org/4.x/) — Choose for fast, classical computer vision and image/video processing: filtering, transfor
- [pandas](https://pandas.pydata.org/docs/) — The default for labeled, heterogeneous tabular data analysis, ETL, and time series in Pyth
- [pillow](https://pillow.readthedocs.io/en/stable/) — Pick Pillow for straightforward image loading/saving, format conversion, thumbnails, cropp
- [polars](https://docs.pola.rs/) — Choose polars for fast, memory-efficient DataFrame work on medium-to-large data, lazy/opti
- [prettier](https://prettier.io/docs/install) — Choose Prettier as the opinionated formatter to eliminate style debates and keep diffs cle
- [prisma](https://www.prisma.io/docs) — Choose Prisma when you want a mature, declarative schema with auto-generated migrations, P
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) — Choose pytest-asyncio when your code uses the stdlib asyncio event loop and you want to wr
- [pytest-cov](https://pytest-cov.readthedocs.io/) — Choose pytest-cov to integrate coverage.py measurement and CI gating directly into a pytes
- [pytorch](https://pytorch.org/docs/stable/) — Primary framework for deep learning research and production: building/training neural netw
- [react-hook-form](https://react-hook-form.com/) — Choose React Hook Form for performant React forms where minimizing re-renders matters; it 
- [recharts](https://recharts.org/) — Choose Recharts for standard React dashboard charts (line, bar, area, pie, scatter) with a
- [redis-py](https://redis.readthedocs.io/en/stable/) — Choose redis-py (the official client) for any Python access to Redis: caching, rate limiti
- [requests](https://requests.readthedocs.io/) — Choose requests for straightforward synchronous HTTP in scripts, CLIs, and small services 
- [rich](https://rich.readthedocs.io/) — Choose Rich to add color, tables, progress bars, markdown, and beautiful tracebacks to ter
- [scikit-learn](https://scikit-learn.org/stable/) — Go-to for classical/tabular machine learning (linear models, trees, ensembles, SVMs, clust
- [socket.io](https://socket.io/docs/v4/) — Choose Socket.IO for real-time bidirectional features (chat, live dashboards, presence, no
- [sqlite-vec](https://alexgarcia.xyz/sqlite-vec/) — Choose sqlite-vec for fast, embedded, dependency-free vector search that lives inside a SQ
- [structlog](https://www.structlog.org/en/stable/) — Choose structlog when you want structured, machine-parseable (JSON) logs with bound contex
- [tenacity](https://tenacity.readthedocs.io/en/stable/) — Choose tenacity to add configurable retry/backoff to flaky calls (network, DB, third-party
- [three.js](https://threejs.org/docs/) — Use three.js for general-purpose 3D/WebGL: scenes, models, shaders, and visualizations in 
- [typer](https://typer.tiangolo.com/) — Choose Typer for new Python CLIs when you want the least boilerplate and type-hint-driven 
- [vitest](https://vitest.dev/guide/) — Choose Vitest for any Vite-based or ESM/TypeScript project—it shares Vite's config and tra
- [zod](https://zod.dev/) — Use Zod for runtime validation of untrusted input (API payloads, env vars, form data) with

## orm
- [SQLAlchemy 2.0 (async)](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — Use when building non-blocking, IO-concurrent apps (e.g. asyncio/FastAPI services) that ne

## recipe
- [asyncio 'Event loop is closed' (pytest-asyncio 1.x async DB tests)](https://pytest-asyncio.readthedocs.io/en/stable/concepts.html) — 'RuntimeError: Event loop is closed' in pytest when testing FastAPI + SQLAlchemy async + a
- [asyncpg / SQLAlchemy 'got Future attached to a different loop'](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — RuntimeError about a Future/Task attached to a different event loop, usually outside the w
- [FastAPI + Vite/React: blocked by CORS policy](https://fastapi.tiangolo.com/tutorial/cors/) — Vite dev SPA (port 5173) cannot call the FastAPI backend (port 8000); browser console show
- [FastAPI 422 Unprocessable Entity (request body validation)](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/) — FastAPI returns HTTP 422 with a detail array; the request never reaches handler logic beca
- [FastAPI async DB session dependency (leaks / blocking-in-async)](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/) — Pool exhaustion, leaked DB connections, or poor concurrency in FastAPI; deciding between a
- [Pydantic v1 -> v2 migration (orm_mode/from_orm/validator removed)](https://pydantic.dev/docs/validation/latest/get-started/migration/) — Errors/deprecation warnings after upgrading to Pydantic v2: from_orm/orm_mode, .dict()/.js
- [Python circular import / partially initialized module (FastAPI projects)](https://docs.python.org/3/reference/import.html) — Startup-time ImportError 'cannot import name ... from partially initialized module (most l
- [React 19: Hydration failed (server/client mismatch)](https://react.dev/reference/react-dom/client/hydrateRoot) — An SSR/SSG React app logs a hydration mismatch in the browser console.
- [React useEffect: stale closure / missing dependency (exhaustive-deps)](https://react.dev/reference/react/useEffect) — Effect uses outdated state/props, or ESLint react-hooks/exhaustive-deps flags a missing de
- [React/TS: Cannot read properties of undefined (reading 'map')](https://react.dev/learn/conditional-rendering) — Component throws a TypeError accessing a property/method (often .map) on data that is stil
- [React: infinite re-render / Maximum update depth exceeded](https://react.dev/reference/react/useEffect) — Component re-renders endlessly or React throws 'Maximum update depth exceeded'.
- [React: Rendered more hooks than during the previous render](https://react.dev/reference/rules/rules-of-hooks) — React component crashes on re-render with an Invariant Violation about hook count changing
- [SQLAlchemy 2.0 async MissingGreenlet (greenlet_spawn has not been called)](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — MissingGreenlet / 'greenlet_spawn has not been called; can't call await_only() here' raise
- [SQLAlchemy DetachedInstanceError / post-commit attribute access (async)](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — DetachedInstanceError ('not bound to a Session') or unexpected reload errors when touching
- [Vite: import.meta.env.VITE_* is undefined](https://vite.dev/guide/env-and-mode) — Environment variables read as undefined via import.meta.env in a Vite + React app.

## security
- [OWASP A01:2025 — Broken Access Control / IDOR (BOLA)](https://owasp.org/Top10/2025/A01_2025-Broken_Access_Control/) — Any endpoint that loads/mutates a resource by ID, any admin/privileged route, or when a us
- [OWASP A02:2025 — Security Misconfiguration & CORS (FastAPI)](https://owasp.org/Top10/2025/A02_2025-Security_Misconfiguration/) — Configuring CORSMiddleware, deploying to production, exposing API docs, or setting HTTP se
- [OWASP A03:2025 — Software Supply Chain Failures (uv / npm deps)](https://owasp.org/Top10/2025/A03_2025-Software_Supply_Chain_Failures/) — Adding/updating Python or npm dependencies, setting up CI, or reviewing the dependency tre
- [OWASP A04:2025 — Cryptographic Failures / Secrets Management](https://owasp.org/Top10/2025/A04_2025-Cryptographic_Failures/) — Handling any secret (DB connection string, JWT signing key, API keys), configuring TLS, or
- [OWASP A05:2025 — Injection (SQLi in SQLAlchemy 2.0)](https://owasp.org/Top10/2025/A05_2025-Injection/) — Whenever building queries with any user-controlled value, especially raw SQL via text() or
- [OWASP A06:2025 — Insecure Design / XSS & Input Validation (React + Pydantic)](https://owasp.org/Top10/2025/A06_2025-Insecure_Design/) — Rendering user-controlled content in React, designing validation strategy, or threat-model
- [OWASP A07:2025 — Authentication Failures (JWT, Argon2/bcrypt)](https://owasp.org/Top10/2025/A07_2025-Authentication_Failures/) — Designing or reviewing login, token issuance/verification, password storage, session/refre
- [OWASP A09:2025 — Security Logging & Alerting Failures](https://owasp.org/Top10/2025/A09_2025-Security_Logging_and_Alerting_Failures/) — Setting up logging/observability, incident-response readiness, or reviewing what gets reco
- [OWASP API4:2023 — Unrestricted Resource Consumption / Rate Limiting (slowapi)](https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/) — Public/auth endpoints exposed to abuse, brute-force, or scraping; any endpoint returning l
- [OWASP API7:2023 — Server-Side Request Forgery (SSRF)](https://owasp.org/API-Security/editions/2023/en/0xa7-server-side-request-forgery/) — Any feature where the server makes outbound requests to a URL influenced by the client (we

## testing
- [pytest](https://docs.pytest.org/en/stable/) — Use pytest as the de-facto framework for writing and running automated tests in Python - f

## tooling
- [Pydantic v2](https://docs.pydantic.dev/latest/) — Use Pydantic v2 to define type-hinted data models that validate, coerce, and serialize unt
- [Ruff](https://docs.astral.sh/ruff/) — Use Ruff as a single, extremely fast (Rust-based) drop-in replacement for Flake8, isort, p
- [uv (Python packaging)](https://docs.astral.sh/uv/) — Use uv as a single, extremely fast Rust-based tool to replace pip, pip-tools, virtualenv, 
- [Vite](https://vite.dev/guide/) — Use Vite as the dev server and build tool for modern web/SPA projects (vanilla or framewor

## web-framework
- [Express](https://expressjs.com/) — Use Express when you want a fast, minimal, unopinionated Node.js framework to build HTTP A
- [FastAPI](https://fastapi.tiangolo.com/) — Use FastAPI to build high-performance, type-safe Python REST/JSON APIs (and async backends
