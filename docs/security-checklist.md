# Security checklist (OWASP)

> IMPORTANT (mid-2026): **OWASP Top 10:2025** is the current web edition (8th installment, released late 2025) and supersedes 2021. The **OWASP API Security Top 10:2023** is still the current API edition. The mapping below uses the current editions; the 2021 IDs are noted in parentheses where they shifted.
>
> Stack-specific note: the **official FastAPI security tutorial now recommends `pwdlib` (Argon2) and `PyJWT`**, replacing the older `passlib` + `python-jose` combo. `python-jose` is effectively unmaintained — prefer `PyJWT`.

Stack context: FastAPI + SQLAlchemy 2.0 async + PostgreSQL + React 19.

### 1. Broken Access Control / IDOR — A01:2025, API1:2023 (BOLA) + API5:2023 (BFLA)
- [ ] **Never trust the object ID in the path/body.** Every endpoint that loads a resource by ID (`/orders/{id}`) MUST re-check the authenticated user owns or is authorized for that row — `WHERE id = :id AND owner_id = :current_user_id`. This is the #1 risk in both lists.
- [ ] Enforce ownership in the query, not after fetching (avoids leaking existence via timing/404-vs-403).
- [ ] Use FastAPI dependencies (`Depends(get_current_user)`) consistently; default-deny — protect routes explicitly rather than relying on a global "open" default.
- [ ] Check function-level authz (BFLA): admin routes must verify role/scope, not just authentication. Don't rely on the frontend hiding a button.
- [ ] In React: client-side route guards are UX only — they are NOT security. All authorization must be server-enforced.

### 2. Injection / SQLi — A05:2025 (was A03:2021), API-relevant
- [ ] **Use the ORM / parameterized queries.** SQLAlchemy 2.0 `select()` and `session.execute(text("... :p"), {"p": val})` bind parameters safely.
- [ ] **Never f-string / `.format()` / `%` user input into SQL**, even inside `text()`. `text(f"... {user_input}")` is the classic hole.
- [ ] Identifiers (table/column names) can't be bound — if dynamic, validate against an allowlist, never interpolate raw.
- [ ] Validate all input with Pydantic models (also mitigates command/NoSQL/template injection paths).

### 3. Authentication Failures — A07:2025 (was A07:2021), API2:2023
- [ ] Hash passwords with **Argon2 (`pwdlib[argon2]`, `PasswordHash.recommended()`)** or bcrypt. Never store plaintext or fast hashes (MD5/SHA-256-unsalted).
- [ ] JWTs: sign with a strong secret/asymmetric key; **always verify signature, `exp`, and `aud`/`iss`** on decode (`jwt.decode(..., algorithms=["HS256"], audience=...)`). Pin `algorithms=[...]` — never accept `alg: none`.
- [ ] Short-lived access tokens (e.g. 15 min) + rotating refresh tokens; implement logout/revocation (refresh-token denylist) since JWTs are stateless.
- [ ] Rate-limit login/refresh endpoints; enforce account lockout/backoff on credential stuffing.
- [ ] If storing tokens in the browser: prefer `HttpOnly` + `Secure` + `SameSite` cookies over `localStorage` (XSS-exfiltration resistant). If using cookies, add CSRF protection.

### 4. Cryptographic Failures / Secrets — A04:2025 (was A02:2021)
- [ ] Serve everything over **HTTPS/TLS only**; enable HSTS at the edge.
- [ ] Load secrets (DB URL, JWT key) from environment / a secrets manager — never commit `.env`; never hardcode in source or ship to the React bundle (anything in a Vite `VITE_` var is public).
- [ ] Rotate keys; use distinct secrets per environment.

### 5. Security Misconfiguration & CORS — A02:2025 (up from A05:2021), API8:2023
- [ ] **CORS:** set `allow_origins` to an explicit list. **Do not combine `allow_credentials=True` with `allow_origins=["*"]`** — it's rejected/insecure. Restrict `allow_methods`/`allow_headers`.
- [ ] Disable interactive docs (`/docs`, `/redoc`) and verbose tracebacks in production (`debug=False`); return generic error bodies (ties to A10:2025 Mishandling of Exceptional Conditions).
- [ ] Set security headers (CSP, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `X-Frame-Options`/frame-ancestors) via middleware or reverse proxy.

### 6. Unrestricted Resource Consumption / Rate Limiting — API4:2023
- [ ] Add rate limiting (e.g. **slowapi** for FastAPI/Starlette) with a Redis backend for multi-instance deployments; return 429 on exceed.
- [ ] Cap request body size, pagination limits, and query depth/complexity to prevent resource exhaustion / DoS.

### 7. SSRF — API7:2023 (also part of A01:2021's old SSRF; now distinct in API list)
- [ ] If the backend fetches user-supplied URLs (webhooks, image proxies, integrations): validate against an **allowlist of hosts/schemes**, block private/link-local ranges (169.254.169.254, 10/8, 127/8), and disable redirects to internal targets.

### 8. Software Supply Chain & Integrity — A03:2025 (NEW, major), A08:2025
- [ ] Pin and lock dependencies (`uv.lock`); audit with `pip-audit`/`uv` advisories and `npm audit` for the React SPA. This is now A03 in 2025 — a top-3 risk.
- [ ] Verify integrity of third-party scripts (SRI) and CI artifacts; minimize transitive deps.

### 9. Logging & Alerting — A09:2025
- [ ] Log authn/authz failures, access-control denials, and input-validation failures — without logging secrets/PII/tokens. Alert on anomalies.

### 10. Insecure Design / XSS in React — A06:2025, A03:2021 (XSS now under Injection)
- [ ] React escapes by default; **avoid `dangerouslySetInnerHTML`** — if unavoidable, sanitize (DOMPurify). Treat XSS as the primary token-theft vector.
- [ ] Validate/normalize all input server-side with Pydantic regardless of client validation.
