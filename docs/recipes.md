# Error -> fix recipes

Stack context: FastAPI + SQLAlchemy 2.0 async ORM + asyncpg + Pydantic v2 backend, React 19 + TypeScript + Vite SPA. Verified against official docs (docs.sqlalchemy.org, pydantic.dev, fastapi.tiangolo.com, react.dev, vite.dev) as of mid-2026.

## Python / FastAPI / SQLAlchemy 2.0 async / Pydantic v2 / asyncpg

Stack assumptions: FastAPI, SQLAlchemy 2.0 async ORM (`create_async_engine` + `AsyncSession`), `asyncpg` driver (`postgresql+asyncpg://`), Pydantic v2, Python 3.11+/uv.

### 1. `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here`

- **Symptom:** Raised when serializing an ORM object or accessing an attribute — typically `obj.some_relationship` or a deferred/expired column inside an async route, often only after `await session.commit()`.
- **Root cause:** A *lazy load* (implicit IO) is triggered outside of an `await`. The async engine cannot transparently run blocking IO; lazy loading and post-commit attribute refresh are **not supported** under asyncio. ([SQLAlchemy asyncio docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html))
- **Fixes (pick the one that matches the access pattern):**
  1. **Eager-load relationships in the query:** `select(A).options(selectinload(A.bs))` — `selectinload()` is the recommended async eager loader (collections); use `joinedload()` for many-to-one. ([docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html))
  2. **Set `expire_on_commit=False`** on the session factory so attributes already loaded survive `commit()` (see #2 below).
  3. **`AsyncAttrs` mixin** (SQLAlchemy >= 2.0.13): add to your `Base`, then `await obj.awaitable_attrs.bs` to lazily load *with* an await. ([docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html))
  4. **`lazy="raise"`** on relationships to convert silent lazy loads into a loud, early error so you must eager-load explicitly.
  5. Run legacy sync-style code via `await session.run_sync(fn)` which provides a greenlet context.

### 2. `DetachedInstanceError: Instance <X> is not bound to a Session` (and the post-commit variant)

- **Symptom:** Accessing an attribute after the session closed, or after `commit()`, raises `DetachedInstanceError` or a `MissingGreenlet` triggered by re-load.
- **Root cause:** By default `commit()` **expires all attributes**; next access re-loads from the DB — impossible if the object is detached or under asyncio. ([Session API docs](https://docs.sqlalchemy.org/en/21/orm/session_api.html))
- **Fix:** Configure the async session factory with `expire_on_commit=False`. Official async docs explicitly recommend this "so that we may access attributes on an object subsequent to a call to `AsyncSession.commit()`." If a row was changed externally and you need fresh data, call `await session.refresh(obj)` explicitly. Also ensure objects aren't used after the `async with session:` block closes. ([asyncio docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html))

### 3. `RuntimeError: Task <...> got Future <...> attached to a different loop`

- **Symptom:** Works in the app, fails in tests / scripts that call `asyncio.run()` more than once, or share one engine across event loops.
- **Root cause:** An `asyncpg` connection is bound to the loop that created it and **cannot be reused on another event loop**; the SQLAlchemy pool holds it across loops. ([discussion](https://github.com/sqlalchemy/sqlalchemy/discussions/12211))
- **Fixes:** Create/dispose the engine per loop — `await engine.dispose()` before reuse on a new loop; **or** configure the engine with `poolclass=NullPool` so no connection is reused across loops. ([asyncio docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html))

### 4. `RuntimeError: Event loop is closed` (mostly in tests)

- **Symptom:** Async DB teardown fails with "Event loop is closed", typically in pytest with a session-scoped engine and function-scoped tests.
- **Root cause:** Loop lifecycle mismatch — the loop a connection was created on is closed before the resource's async finalizer runs; or two competing loop fixtures. ([pytest-asyncio #991](https://github.com/pytest-dev/pytest-asyncio/issues/991))
- **Fix (mid-2026):** `pytest-asyncio` **1.x removed the overridable `event_loop` fixture**. Do NOT redefine `event_loop`. Instead set `asyncio_mode = auto` and pin loop scope with `asyncio_default_fixture_loop_scope = session` (in `pyproject.toml`/`pytest.ini`) and `@pytest.mark.asyncio(loop_scope="session")`, so the async engine, fixtures, and tests share one loop. Dispose the engine in a session-scoped fixture's teardown. ([pytest-asyncio 1.4 concepts](https://pytest-asyncio.readthedocs.io/en/stable/concepts.html))

### 5. Pydantic v1 -> v2 migration breakage (`ConfigError` / `AttributeError: from_orm` / deprecation warnings)

- **Symptom:** `orm_mode`/`from_orm`/`.dict()`/`@validator`/`@root_validator` no longer work or warn loudly.
- **Root cause:** v2 renamed the public API. Exact replacements ([Pydantic migration guide](https://pydantic.dev/docs/validation/latest/get-started/migration/)):
  | V1 | V2 |
  |---|---|
  | `class Config: orm_mode = True` | `model_config = ConfigDict(from_attributes=True)` |
  | `Model.from_orm(obj)` | `Model.model_validate(obj)` (with `from_attributes=True`) |
  | `Model.parse_obj(d)` | `Model.model_validate(d)` |
  | `m.dict()` / `m.json()` | `m.model_dump()` / `m.model_dump_json()` |
  | `@validator` | `@field_validator` (no `each_item`; annotate the item type instead) |
  | `@root_validator` | `@model_validator(mode="before"/"after")` |
  | `allow_population_by_field_name` | `populate_by_name` |
  | `Field(regex=...)` | `Field(pattern=...)` |
  | `min_items`/`max_items` | `min_length`/`max_length` |
  | `const=True` / `allow_mutation=False` | removed / `frozen=True` |
- **Gotcha:** v2 validates nested models in Rust from the *outermost* schema — submodel `model_validate` is not called recursively, so custom per-submodel validation must be expressed via the schema, not python-side calls.

### 6. FastAPI `422 Unprocessable Entity`

- **Symptom:** Request rejected before your code runs; response body has a `detail` list of `{loc, msg, type}`.
- **Root cause:** Pydantic validation of the request failed. FastAPI parses JSON -> builds the model -> validation error -> 422. ([FastAPI / Pydantic error model](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/))
- **Fix:** Read `loc` — `["body","field"]` = wrong/missing body field; `["query","x"]` = wrong param location. Common causes: client sent a bare scalar/array where a model was expected; missing required field; type mismatch. To accept a single value in the JSON body keyed by name, use `param: int = Body(embed=True)`. To accept a top-level JSON array, type the body as `list[Model]`.

### 7. Circular import / `ImportError: cannot import name 'X' from partially initialized module`

- **Symptom:** App fails at startup; module A imports B which imports A (common between `models.py`, `schemas.py`, `crud.py`, routers).
- **Root cause:** Module still executing when another tries to import a name from it.
- **Fixes:** (a) Put type-only imports under `if TYPE_CHECKING:` and quote the annotations (or add `from __future__ import annotations`); (b) move the import inside the function (deferred/late import); (c) `import module` and reference `module.name` instead of `from module import name`; (d) extract shared definitions into a third module. ([Rollbar guide](https://rollbar.com/blog/how-to-fix-circular-import-in-python/))

### 8. Async dependency / session-leak pitfalls

- **Symptom:** Connection pool exhaustion, or one slow blocking call stalls all requests.
- **Root cause:** Mixing sync blocking DB calls in async routes, or not closing the session.
- **Fix:** Use an `async def` dependency with `yield` that wraps `async with async_session() as session:` so the session always closes (even on exception). Keep it async all the way — a single blocking call in a hot path negates async benefits; for genuinely blocking work use a `def` (sync) endpoint so FastAPI runs it in a threadpool. ([FastAPI deps-with-yield](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/))

---

## React 19 / TypeScript / Vite / Browser

Stack context: React 19 + Vite SPA talking to a FastAPI + SQLAlchemy async backend.

### 1. "Rendered more hooks than during the previous render" (Invariant Violation)
- **Symptom:** Crash on re-render; React counts a different number of hooks than the previous render.
- **Cause:** A Hook (`useState`/`useEffect`/custom hook) is called conditionally — inside an `if`, loop, `try/catch/finally`, nested function, or **after an early `return`**. React identifies hooks by call order, so a missing/extra call desyncs the list.
- **Fix:** Call **all** hooks unconditionally at the top level of the component/custom-hook, *before* any early return. Move the condition *inside* the hook (`useEffect(() => { if (x) {...} }, [x])`) rather than guarding the hook call. Enable `eslint-plugin-react-hooks` (`react-hooks/rules-of-hooks`) to catch this at lint time.
- Exact rule (react.dev): "Don't call Hooks inside loops, conditions, nested functions, or `try`/`catch`/`finally` blocks. Instead, always use Hooks at the top level of your React function, before any early returns."

### 2. Stale closure in `useEffect` / "React Hook useEffect has a missing dependency"
- **Symptom:** Effect (interval, timeout, event listener, subscription) reads an old value of state/props; or `react-hooks/exhaustive-deps` warns about a missing dependency.
- **Cause:** A reactive value (prop, or variable/function declared in the component body) is used inside the Effect but omitted from the dependency array. The closure captured a frozen snapshot from the render that created it.
- **Fix:** Declare every reactive value used by the Effect in the deps array — you cannot "choose" deps; they are determined by the code. For `setState` based on prior state, use the updater form `setCount(c => c + 1)` so `count` is not a dependency and no stale value is captured. For values you must read but not react to, use `useEffectEvent` (omit it from deps — Effect Events are non-reactive).

### 3. Infinite re-render loop (Effect or render)
- **Symptom:** Component re-renders forever / "Maximum update depth exceeded"; Effect runs every render.
- **Cause:** (a) `setState` called unconditionally during render; (b) an Effect sets state and lists that state (or an object/array/function literal) as a dependency. Objects/arrays/functions are compared by reference, so a freshly-created one is "new" every render -> deps always change -> Effect re-runs -> state changes -> loop.
- **Fix:** Never call `setState` directly in the render body. Use the updater form to drop the state dependency. Move object/function creation *inside* the Effect, or memoize with `useMemo`/`useCallback`. Verify deps by logging the array and comparing with `Object.is()` across renders.

### 4. Missing dependency array warning (`exhaustive-deps`)
- **Symptom:** Lint warning: "React Hook useEffect/useMemo/useCallback has a missing dependency."
- **Cause:** The hook references a reactive value not listed in its dependency array.
- **Fix:** Add the value to the array. If adding it causes a loop, address the *reason* (use the updater function, move the object inside, memoize, or use `useEffectEvent`) — do **not** silence the rule with an eslint-disable comment, which reintroduces stale-closure bugs.

### 5. CORS error: "Access to fetch at 'http://localhost:8000/...' from origin 'http://localhost:5173' has been blocked by CORS policy"
- **Symptom:** Browser blocks the Vite dev SPA (port 5173) from calling the FastAPI backend (port 8000); preflight `OPTIONS` fails or response has no `Access-Control-Allow-Origin`.
- **Cause:** FastAPI sends no CORS headers by default; the SPA and API are different origins.
- **Fix:** Add `CORSMiddleware` early (before routes). `from fastapi.middleware.cors import CORSMiddleware` then `app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])`. **Critical:** if `allow_credentials=True` (cookies / `Authorization`), none of `allow_origins`, `allow_methods`, `allow_headers` may be `["*"]` — they must be explicit. Per FastAPI docs: "None of `allow_origins`, `allow_methods` and `allow_headers` can be set to `['*']` if `allow_credentials` is set to `True`." Use `allow_origin_regex` for dynamic origins. Defaults: `allow_methods=['GET']`, `allow_headers=[]`, `allow_credentials=False`.

### 6. Hydration mismatch (only with SSR; React 19 single-diff message)
- **Symptom:** "Hydration failed because the server rendered HTML didn't match the client. As a result this tree will be regenerated on the client." React 19 now prints one consolidated error **with a `+ client / - server` diff** instead of multiple duplicate warnings.
- **Cause:** Server HTML != first client render. Common triggers (from React's own message): `if (typeof window !== 'undefined')` branches, `Date.now()`/`Math.random()`, locale-dependent date formatting, external data not snapshotted into the HTML, invalid HTML nesting, or a browser extension mutating the DOM before React loads.
- **Fix:** Render identical markup on both sides; move client-only/browser-API logic into `useEffect` (post-hydration). For an unavoidable single-element difference (e.g., a timestamp), add `suppressHydrationWarning={true}` (one level deep only — escape hatch, do not overuse). Note: a pure Vite SPA without SSR does not hydrate, so this rarely applies unless you adopt SSR/SSG.

### 7. "Cannot read properties of undefined (reading 'map'/'length'/...)"
- **Symptom:** Runtime TypeError when mapping/accessing data that hasn't loaded yet (async fetch in flight).
- **Cause:** State/prop is `undefined` (or `null`) on first render before the awaited data arrives; you call `.map()` on it.
- **Fix:** Initialize list state to `[]` (`useState<Item[]>([])`); for objects use optional chaining + nullish fallback (`data?.items ?? []`). Gate rendering with a loading flag (`if (loading) return <Spinner/>`). Enable TypeScript `strictNullChecks` (`strict: true`) so the compiler forces you to handle `undefined` before access.

### 8. `import.meta.env.VITE_X` is `undefined`
- **Symptom:** Env var reads as `undefined` in the browser bundle.
- **Cause:** Most common: the variable lacks the `VITE_` prefix — Vite only exposes `VITE_*` to client code (security feature; everything else stays server-side). Other causes: `.env` not in project root (next to `vite.config.ts`/`package.json`); dev server not restarted after editing `.env`; the value wasn't present at **build time** (env is inlined at build, not read at runtime).
- **Fix:** Prefix with `VITE_` and access `import.meta.env.VITE_API_URL`. Restart `vite` after `.env` changes. For TS IntelliSense, augment in `src/vite-env.d.ts` (no `import` statements in this file or augmentation breaks): `interface ImportMetaEnv { readonly VITE_APP_TITLE: string }` and `interface ImportMeta { readonly env: ImportMetaEnv }`. To change the prefix, set the `envPrefix` config option. Built-ins always present: `MODE`, `BASE_URL`, `PROD`, `DEV`, `SSR`.

### React 19 error-handling notes
- Console error **duplication is gone**: a caught/uncaught error is logged once with full info.
- New root options alongside `onRecoverableError`: `onCaughtError` (caught by an Error Boundary) and `onUncaughtError` (not caught).
- `ref` is now a regular prop on function components — `forwardRef` no longer needed; ref callbacks may return a cleanup function.
