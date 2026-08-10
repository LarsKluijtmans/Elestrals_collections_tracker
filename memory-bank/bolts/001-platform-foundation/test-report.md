---
bolt: 001-platform-foundation
stage: test
status: partial
created: 2026-08-09T12:00:00Z
---

# Test Report: 001-platform-foundation

## Automated

```
backend/.venv → pytest tests/ -q
..........                                    [100%]
10 passed in 0.36s
```

| Suite | Covers |
|---|---|
| `test_redaction.py` (7) | sensitive keys, nested structures, bearer/JWT in free text, **validation-error echo**, query strings, never-raises, bounded depth |
| `test_log_routing.py` (3) | error/critical forward · security forwards at any level · routine entries stay local |

## Verified by execution

- `app.main` imports cleanly against real dependencies (not just a syntax check).
- OpenAPI generates four endpoints, each with a summary and response model:
  `GET /api/v1/health` · `GET /api/v1/me` · `PATCH /api/v1/me` · `POST /api/v1/events`
- The admin SDK links from the monorepo (`pip install -e ../auth/packages/python/admin-sdk-python`);
  `0.2.0` is not on PyPI, exactly as app-starter documents.

## A real bug the tests caught

`redact()` originally inspected **key names only**. A FastAPI validation error puts the
offending value under the neutral key `input`, with the sensitive name inside `loc`:

```python
{"loc": ["body", "client_secret"], "msg": "field required", "input": "s3cr3t"}
```

Key-name matching misses that completely — the secret would have been written to `app_logs`
verbatim. This is precisely the leak the platform standards call out, and it failed on the
first run.

Fixed by adding a dict-level rule: when a `loc` contains a sensitive name, the sibling
`input`/`value`/`ctx` keys are redacted too. `main.py` independently whitelists validation
errors down to `loc`/`msg`/`type`, so the application path now has two layers rather than a
gap.

## Not yet verified — requires a running platform

These are the acceptance criteria that cannot be asserted without a live login-api, and they
are the reason this report is `partial` rather than `complete`:

- [ ] Sign in → `/dashboard` → sign out
- [ ] **Blocking check 1**: JWT `sub` stable across an email change
- [ ] **Blocking check 2**: all seven M2M scopes granted (code is in place and fails loudly, unrun)
- [ ] Branding change → chrome changes, element colours do not
- [ ] One `app_logs` row per request (needs the `elestrals` database)
- [ ] Error visible in the platform console
- [ ] Feature-usage event visible in the console
- [ ] logs-api stopped → requests still succeed
- [ ] Token validation < 5ms p95, logging < 3ms p95

## Frontend build

```
npm run typecheck   → clean
npm run build       → ✓ 5009 modules transformed, built in 9.73s
                      dist/assets/index-*.js  906 kB (286 kB gzip)
```

The bundle exceeds Vite's 500 kB warning threshold. Acceptable for a foundation with no
code-splitting yet; revisit with route-level `lazy()` in bolt 006, when there are real pages
worth splitting.

### MUI 9 breaking change, found by the typecheck

Twelve errors, all one class: **MUI 9 removed system props from `Typography` and `Stack`** —
`fontWeight`, `letterSpacing`, `alignItems` and `justifyContent` must now go through `sx`, and
`primaryTypographyProps` is replaced by `slotProps`. All twelve fixed. This is the concrete
cost of the tech-stack correction made during planning: had the plan's original "React 18 +
MUI 5" been believed, none of this would have surfaced until much later.

## Story 002 is now complete

The router **is** mounted: `BrowserRouter` in `App.tsx`, `<Routes>` in `Gate`, `NAV_ROUTES`
driving the rail via `RouterLink`, and active state from `useLocation()` rather than a prop
that would drift. Placeholder pages name the bolt that replaces each one.

The deep-link criterion holds by construction: because login is **embedded** rather than a
redirect, the URL is never touched during sign-in — pasting `/wishlist` while signed out,
authenticating, and landing on `/wishlist` needs no return-path plumbing at all.

## Repository hygiene

Added `.gitignore` — the repo had none, and now contains `node_modules/`, `.venv/` and
`dist/`. Verified by `git check-ignore` that all three are ignored, and that `.env` is
excluded while `.env.example` stays tracked. app-starter's `.env` was deliberately **not**
copied during the fork, so no M2M secret ever entered this repository.

## Coverage

Not measured. The suite covers the two pieces with real logic — redaction and log routing.
The rest of the bolt is wiring whose correctness is established by the runtime checks above,
not by unit tests over framework glue. Coverage gating starts at bolt 002, where the domain
begins.

## Run it

```powershell
# backend
cd backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e ..\..\auth\packages\python\admin-sdk-python   # until 0.2.0 is published
copy .env.example .env          # fill DATABASE_URL + M2M_CLIENT_ID/SECRET
# CREATE DATABASE elestrals CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 9000 --reload

# frontend
cd frontend
npm install
copy .env.example .env          # fill VITE_LOGIN_CLIENT_ID
npm run dev
```
