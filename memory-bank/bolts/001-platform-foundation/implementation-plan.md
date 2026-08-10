---
bolt: 001-platform-foundation
stage: plan
status: awaiting-approval
created: 2026-08-09T12:00:00Z
---

# Implementation Plan: 001-platform-foundation

Stage 1 of 3. **Human checkpoint** — approve before Stage 2 (implement).

## Objective

A running, signed-in, themed, observable application with an empty domain. Six stories, no Elestrals
logic. Every later bolt starts from working rather than blank.

## Two blocking checks, before any other work

Both are cheap, and both change the shape of this bolt if they fail. Neither should be discovered
later.

1. **Is the JWT `sub` stable across an email change?** Every row we own is keyed on it. Verify by
   signing in, changing the email in the platform's `/account`, signing in again, and comparing the
   claim.
2. **Can an M2M service account be provisioned with all seven scopes** — `users:read`, `logs:write`,
   `usage:write`, `notifications:send`, `notifications:configure`, `storage:read`, `storage:write`?
   A missing scope shows up later as a silent 403 inside a call that swallows errors by design, so
   the app asserts all seven at startup in non-prod and fails loudly.

## Files

### Fork from `../app-starter`

Copy, rename, keep the plumbing intact — `security.py`, `admin.py` and `project_logger.py` encode
platform conventions that are easy to get subtly wrong.

```
frontend/                      from app-starter/frontend
backend/                       from app-starter/backend
```

Rename `app-starter-frontend` → `elestral-vault-frontend`; `LOG_CATEGORY=app-starter` → `elestrals`.

### Backend — new

```
backend/app/
  core/
    db.py                  engine, SessionLocal, Base
    dependencies.py        DI wiring — every service wire goes here
    config.py              (extend) DATABASE_URL, ENABLE_* flags
  models/
    base.py                UuidPrimaryKeyMixin, TimestampMixin
    app_log.py             app_logs
    user_profile.py        user_profiles
  repositories/
    app_log_repository.py
    user_profile_repository.py
  services/
    logging_service.py     log_event()  ← the ONLY log writer
    usage_service.py       usage_track()
    profile_service.py     ensure_profile(), get_profile()
  controllers/
    health.py              GET /api/v1/health
    me.py                  GET/PATCH /api/v1/me
    events.py              POST /api/v1/events
  middleware/
    logged_route.py        one app_logs row per request
    redaction.py           strip secrets BEFORE persistence
alembic/
  env.py
  versions/0001_app_logs_and_user_profiles.py
```

New deps: `sqlalchemy>=2.0`, `alembic>=1.13`, `pymysql`, `apscheduler`, `pytest`, `pytest-asyncio`.

### Frontend — new

```
frontend/src/
  theme/
    domain.ts              8 element hues + rarity materials — CONSTANTS, never branded
    tokens.ts              chrome tokens from branding, light + dark
  components/
    AppShell.tsx           (replace) rail + top bar + responsive collapse
    NavRail.tsx
    TopBar.tsx
    ErrorBoundary.tsx
    PlatformUnavailable.tsx
  routes.tsx               phase-1 route table
  pages/
    Dashboard.tsx          placeholder — real one is bolt 006
    Settings.tsx           placeholder — real one is bolt 009
  api/client.ts            (extend) typed fetch with Bearer + error-shape parsing
```

### Database

`elestrals` on the platform's MySQL `:3306`. Migration `0001` creates `app_logs` and
`user_profiles` per `standards/data-model.md`, with the indexes named there.

## Story mapping

| Story | Lands as |
|---|---|
| 001-sign-in-with-platform | inherited from app-starter; verified, plus the "platform unavailable" screen |
| 002-app-shell-and-routing | `AppShell`, `NavRail`, `TopBar`, `routes.tsx`, `ErrorBoundary` |
| 003-branding-driven-theme | `theme/tokens.ts` + `theme/domain.ts` — **the two-layer split** |
| 004-app-logging | `app_logs`, `logging_service.log_event()`, `logged_route`, `redaction` |
| 005-platform-log-forwarding | forwarding branch inside `log_event()`, nowhere else |
| 006-usage-metering | `usage_service.usage_track()` |

## Sequence

1. Blocking checks 1 and 2
2. Fork, rename, both apps run
3. DB + Alembic + `0001` migration
4. `log_event()` + redaction + `logged_route` — **before** any feature, so everything after it is diagnosable
5. Forwarding + `usage_track()`
6. `theme/domain.ts` + `theme/tokens.ts`
7. App shell, routing, error boundary
8. `/health`, `/me`, `/events`
9. Startup scope assertion

Order matters at step 4: logging first means every subsequent step is debuggable.

## Definition of done

- [ ] Sign in → land on `/dashboard` → sign out
- [ ] Change project branding → chrome changes on reload; **element colours do not**
- [ ] One `app_logs` row per request with `request_id`, status, duration
- [ ] Unhandled exception → `critical` row locally **and** in the platform console
- [ ] A feature-usage event visible in the console
- [ ] **logs-api stopped → every request still succeeds**
- [ ] All seven scopes asserted at startup
- [ ] `Authorization` headers never present in `app_logs`, including in validation-error payloads
- [ ] Token validation < 5ms p95, logging < 3ms p95
- [ ] Coverage > 80%

## Risks

| Risk | Mitigation |
|---|---|
| SDK `0.2.0` not on PyPI/npm | `scripts/use-local-sdks.ps1` links from `../auth` — already solved in app-starter |
| Platform not running locally | `../auth/docker-compose.yml`; the "platform unavailable" screen is a story, not an afterthought |
| React 19 / MUI 9 peer conflicts | Versions taken from app-starter's actual `package.json`, not assumed |
| Validator deps missing | Add `fs-extra` + `js-yaml` as devDependencies so the specsmd scripts run without `NODE_PATH` |

## Out of scope

Anything Elestrals. No cards, sets, printings, inventory. `/dashboard` and `/settings` are
placeholders. The catalog is bolt 002.
