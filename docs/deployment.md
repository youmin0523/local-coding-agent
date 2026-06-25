# Deployment guide

Recipes for shipping the kind of projects the developer builds — **FastAPI + SQLAlchemy
async + PostgreSQL** backends and **React 19 + Vite** SPAs. Standard, current practice;
verify exact versions/flags against each tool's official docs before relying on them.

## 1. Containers (Docker)

**FastAPI backend (uv, multi-stage, non-root):**
```dockerfile
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
RUN useradd -m app
WORKDIR /app
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "4", "-b", "0.0.0.0:8000"]
```
**Vite/React (build → static, served by nginx):**
```dockerfile
FROM node:22-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build            # -> /app/dist
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf   # add SPA try_files fallback
```
- Use a `.dockerignore` (`.venv`, `node_modules`, `.git`, `__pycache__`, `dist`).
- Keep images slim (`-slim`/`alpine`), run as non-root, leverage layer caching (copy lockfiles first).

**docker-compose (app + db):**
```yaml
services:
  db:
    image: postgres:16
    environment: { POSTGRES_PASSWORD: ${DB_PASSWORD} }
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck: { test: ["CMD-SHELL", "pg_isready -U postgres"], interval: 5s, retries: 5 }
  api:
    build: ./backend
    environment: { DATABASE_URL: postgresql+asyncpg://postgres:${DB_PASSWORD}@db:5432/app }
    depends_on: { db: { condition: service_healthy } }
    ports: ["8000:8000"]
volumes: { pgdata: {} }
```

## 2. Serving the backend
- Dev: `fastapi dev` / `uvicorn app.main:app --reload`. Prod: **gunicorn with uvicorn workers**
  (`-k uvicorn.workers.UvicornWorker -w <2*cores+1>`), or `uvicorn --workers N`.
- Behind a proxy, pass `--proxy-headers --forwarded-allow-ips='*'` so client IPs/scheme are correct.
- Expose a `GET /health` returning 200 for load-balancer/container healthchecks.
- **Run Alembic migrations on deploy** (`alembic upgrade head`) as a release step *before* new
  app instances serve traffic; never autocreate tables in prod.
- Config/secrets via env vars (pydantic-settings) — never bake secrets into the image.

## 3. Frontend (Vite SPA)
- `npm run build` → `dist/`; serve as static files. Build-time env via `import.meta.env.VITE_*`
  (only `VITE_`-prefixed vars are exposed; they are **public** — no secrets).
- SPA routing needs a history fallback: nginx `try_files $uri /index.html;` (or platform SPA mode).
- Cache hashed assets immutably; keep `index.html` no-cache so new builds are picked up.

## 4. Platforms (pick by need)
- **Vercel / Cloudflare Pages / Netlify** — best for the static SPA (git push → build → CDN); set `VITE_*` build envs in the dashboard.
- **Fly.io** — Docker-native, global VMs + managed Postgres; `fly launch` → `fly deploy`. Good for the FastAPI container + DB together.
- **Railway / Render** — simplest PaaS for API + managed Postgres add-on; connect repo, set env vars, auto-deploy on push.
- **Docker on a VPS** — most control/cheapest at scale; `docker compose up -d` behind a proxy.

## 5. Reverse proxy, TLS, CI/CD
- **Caddy** = automatic HTTPS (Let's Encrypt) with a 2-line Caddyfile — simplest TLS. **nginx**/**Traefik** are the alternatives (Traefik for dynamic Docker routing). Proxy `/api/*` → the API, serve the SPA for everything else.
- **GitHub Actions** deploy pipeline: lint+type+test → build Docker image → push to a registry → deploy (platform CLI / SSH `docker compose pull && up -d`). Keep credentials in repo/Environment **secrets**; gate prod deploys on a protected branch/environment.

> Rule of thumb: SPA on a static/CDN platform, API+DB on Fly/Railway/Render or a VPS with
> Caddy for TLS; migrations as a pre-release step; secrets only via env/secret stores.
