---
name: deploy-web-app
description: Containerize and deploy a FastAPI backend and/or a React+Vite frontend, with secrets in env, a healthcheck, migrations, and CI/CD. Use when asked to deploy, Dockerize, write a Dockerfile or docker-compose, set up CI/CD, or ship a project to Fly/Railway/Render/Vercel/Cloudflare Pages.
license: MIT
metadata:
  version: "1.0"
  author: lca
---

# Deploy a web app

Reference `docs/deployment.md` and the `deployment` reference cards for exact
snippets. Apply these gates in order.

## Pre-flight (do first)

1. **Run `secret_scan`** — no hardcoded keys/tokens may ship. Every secret comes
   from env / platform secrets. Confirm `.env` is git-ignored.
2. Pin dependencies (`uv.lock` / lockfile). Define a `/health` endpoint.

## Backend (FastAPI + SQLAlchemy + PostgreSQL)

- **Multi-stage Dockerfile**: build deps with `uv sync --locked`, copy into a slim
  runtime image, run as a non-root user.
- **Serve** with `gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w <2*cpu+1>`,
  `--proxy-headers` behind a reverse proxy.
- **Migrations** as a release step: `alembic upgrade head` (never auto-migrate at
  request time).
- **compose**: `app` + `db` with a `pg_isready` healthcheck and `depends_on:
  condition: service_healthy`; named volume for Postgres data.

## Frontend (React + Vite)

- `npm run build` → static `dist/`. Build-time env is `VITE_*` only (public).
- Serve via nginx/Caddy with SPA fallback (`try_files $uri /index.html`), or a CDN
  host (Vercel / Cloudflare Pages / Netlify). Immutable cache for hashed assets.

## Reverse proxy + TLS

- **Caddy** for automatic HTTPS (simplest), or nginx/Traefik with Let's Encrypt.
  Proxy `/api/*` to the backend; serve the SPA for everything else.

## Platforms

- **Fly.io / Railway / Render**: Docker-native API + managed Postgres; set secrets
  via the platform, deploy on push.
- **Vercel / Cloudflare Pages**: the static SPA.

## CI/CD (GitHub Actions)

- `on: pull_request` → lint + test. `on: push to main` → build image, push to a
  registry, deploy. Secrets via repo/Environment secrets — never in YAML.

## Validate

- `secret_scan` clean; `.env` ignored.
- Image builds; container starts; `/health` returns 200.
- `alembic upgrade head` runs as a deploy step; SPA deep links don't 404.
