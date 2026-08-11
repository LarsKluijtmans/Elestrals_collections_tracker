---
created: 2026-08-09T12:00:00Z
updated: 2026-08-09T12:00:00Z
---

# Tech Stack

Decided at inception. The Construction Agent loads this file as **critical context** — code it
generates must conform.

## Starting point

Fork **`../app-starter`**. It already wires the four cross-cutting concerns (login, branding, i18n,
platform logging) against the platform, and it mirrors the `auth` monorepo's conventions. We add a
persistence layer, which app-starter deliberately has none of.

## Frontend

| Concern | Choice | Notes |
|---|---|---|
| Framework | React 19 + TypeScript (strict) | from app-starter — verified against its `package.json` |
| Build | Vite | dev on `:5173` |
| UI kit | MUI 9 | themed from resolved platform branding, not hard-coded |
| Icons | lucide-react | already in app-starter |
| Auth | `@lars-kluijtmans/react-auth` + `@lars-kluijtmans/react-login` | embedded `<LoginForm>`, Authorization Code + PKCE |
| Branding | `fetchBranding()` → `themeFromBranding()` | wraps the whole app, not just the login form |
| i18n | i18next, EN + NL | shares one instance with the login UI's `login` namespace |
| Server state | TanStack Query | caching, background refetch, optimistic inventory edits |
| Client state | React context only | no Redux; the domain state is server state |
| Charts | Recharts | price history, portfolio value, completion |
| Tables | TanStack Table + virtualization | collection views reach 10k+ rows |
| Forms | React Hook Form + Zod | Zod schemas shared with API response parsing |
| Routing | React Router v6 | file layout mirrors the page inventory in `ux-guide.md` |

**SPA trade-off, accepted:** public card and listing pages are not server-rendered, so they are not
SEO-indexable. If organic search traffic becomes a goal, the mitigation is a pre-rendered public
surface for `/cards/:id` and `/market/:id` only — not a wholesale move to SSR.

## Backend

| Concern | Choice | Notes |
|---|---|---|
| Framework | FastAPI (Python 3.12) | from app-starter. **`:9500` locally** — `:9000` is taken by platform-management-api |
| Layering | `Controllers → Services → Repositories → SQLAlchemy models → MySQL` | **identical** to every service in `../auth` |
| ORM | SQLAlchemy 2.x | typed `Mapped[]` style |
| Migrations | Alembic, single tree | ours alone — we do not touch `alembic_tenant` |
| Validation | Pydantic v2 | `app/schemas/` |
| Token validation | JWKS, local, `RS256`, `iss` pinned | reuse `app-starter/backend/app/security.py` verbatim |
| Platform calls | `lars-kluijtmans-admin-sdk` (Python) as M2M | server-side only |
| Jobs | APScheduler in-process for phase 1; **Celery + Redis** from phase 2 | scraping needs retries, isolation and a queue |
| HTTP client | `httpx` (async) | scrapers, with per-source rate limiting |
| Testing | pytest + `pytest-asyncio`; SQLite `create_all` for unit, MySQL for integration | mirrors the platform's test split |

### Layering rules (non-negotiable)

- Controllers are thin routers with an explicit `/api/v1` prefix and no DB access.
- Services hold business logic and never touch a session directly.
- Repositories are the only place that touches the DB, and every query scoped to a user filters on
  `user_sub` — the subject claim from the validated JWT, never a client-supplied id.
- Every router uses the logged-route wrapper so requests land in `app_logs`.

## Data

- **MySQL 8.4** — the platform's existing instance, published on host **`:9306`** (container
  `:3306`), in our **own `elestrals` database** with a scoped `elestrals_app` user granted only
  on `elestrals.*`. The app never uses the platform's `app` or root credentials.
- Connection string comes from the platform deployment's environment; the app never provisions
  databases (that is tenant-api's job, and we are not a tenant service).
- Full schema: `standards/data-model.md`.

## Platform integration

> **Ports: container vs host.** The `8xxx` numbers below are the ports each service listens on
> *inside* its container. The platform's `docker-compose.yml` publishes them on **`9xxx` host
> ports**, and that is what a client running outside the compose network must dial. Verified
> against the running stack on 2026-08-11; the mapping comes from `../auth/.env`.

| Concern | Service | Container | **Host** | How |
|---|---|---|---|---|
| Sign-in | login-api | `:8010` | **`:9010`** | PKCE via `react-login`; frontend holds only a `client_id` |
| User enrichment | auth-api | `:8050` | **`:9050`** | backend M2M `users.get`, scope `users:read` |
| Branding | branding-api | `:8080` | **`:9120`** | anonymous `/resolve`; drives the MUI theme |
| Notifications | notification-api | `:8020` | **`:9020`** | backend M2M, scopes `notifications:send`, `notifications:configure` |
| Platform logging | logs-api | `:8030` | **`:9030`** | backend M2M, scope `logs:write` |
| Usage metering | logs-api | `:8030` | **`:9030`** | backend M2M, scope `usage:write` |
| User files | storage-api | `:8070` | **`:9070`** | avatars via `react-auth`'s `useStorage`; listing photos likewise, `owned` access |

**Two credential sets, two homes.** The public login `client_id` lives in the frontend. The M2M
`client_id` + `client_secret` lives **only** in the backend. Never ship the M2M secret to a browser.

### Required M2M RBAC role

One service account, granted: `users:read`, `logs:write`, `usage:write`, `notifications:send`,
`notifications:configure`, `storage:read`, `storage:write`.

## Environments

| | Frontend | Backend | DB |
|---|---|---|---|
| Local | `:5173` | `:9500` | platform MySQL `:9306`, db `elestrals` |
| Prod | static build behind the platform's reverse proxy | container | same MySQL, db `elestrals` |

Deployment follows the platform's `docker-compose.yml` pattern: our two images join the existing
compose project so service discovery and secrets work unchanged.

## Conventions inherited from `../auth`

- `/health` endpoint on the backend, polled by status-api.
- Secrets never logged; authorization headers redacted before persistence.
- Errors classified by category; `security` category for auth failures.
- ADRs for anything structural, in `memory-bank/standards/decision-index.md`.
