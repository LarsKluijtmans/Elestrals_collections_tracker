---
unit: 001-platform-foundation
intent: 001-collection-tracker
phase: inception
status: stories-defined
created: '2026-08-09T12:00:00Z'
updated: '2026-08-09T12:00:00Z'
---

# Unit Brief: platform-foundation

## Purpose

Turn `../app-starter` into this application: a running React + FastAPI pair, signed in against the
platform, themed from platform branding, backed by our own `elestrals` database, and observable
through our own log table with forwarding and usage metering. No Elestrals domain logic lives here.

## Scope

### In Scope
- Fork, rename and de-brand app-starter into `frontend/` and `backend/`
- App shell: left rail, top bar, routing, error boundary, EN/NL, "platform unavailable" screen
- Database creation, Alembic tree, `app_logs` and `user_profiles` migrations
- `log_event()` — one call site, two destinations, redaction built in
- `usage_track()` — feature metering that can never fail a request
- M2M service account provisioning and a startup smoke test of every scope
- Health endpoint, CI, containerisation joining the platform compose project

### Out of Scope
- Any catalog, inventory, price or market table (units 002+)
- Profile *editing* — the `user_profiles` table exists here, its UI is unit 007
- Notification delivery — the outbox is unit 007

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Sign in with the platform (PKCE, embedded LoginForm) | Must |
| FR-2 | Theme the app from platform branding | Must |
| FR-3 | Our own logging table, with platform forwarding | Must |
| FR-4 | Meter feature usage to the platform | Must |

---

## Domain Concepts

### Key Entities
| Entity | Description | Attributes |
|--------|-------------|------------|
| Principal | The validated caller derived from a JWT | `sub`, `company_id`, `project_id`, `is_operator` |
| UserProfile | App-owned preferences over platform identity | `user_sub`, `handle`, `collection_visibility`, `default_currency`, `condition_scale` |
| AppLogEntry | One observable event | `level`, `category`, `component`, `operation`, `message`, `user_sub`, `request_id`, `context`, `trace` |
| UsageEvent | One metered feature use | `feature`, `subject`, `quantity`, `reference_1..3` |

### Key Operations
| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `verify_token` | JWKS-validate a bearer token | Authorization header | `Principal` or 401 |
| `log_event` | Write to `app_logs`; forward if error/critical/security | level, category, message, context | none (never raises) |
| `usage_track` | Record a feature use to logs-api | feature, subject, quantity, refs | none (never raises) |
| `resolve_theme` | Fetch and map platform branding | company/project | MUI theme |
| `ensure_profile` | Lazily create `user_profiles` on first authenticated request | `sub` | `UserProfile` |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 6 |
| Must Have | 6 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 001-sign-in-with-platform | Sign in through the platform | Must | Planned |
| 002-app-shell-and-routing | App shell and routing | Must | Planned |
| 003-branding-driven-theme | Theme from platform branding | Must | Planned |
| 004-app-logging | Our own `app_logs` table | Must | Planned |
| 005-platform-log-forwarding | Forward errors and security events | Must | Planned |
| 006-usage-metering | Meter feature usage | Must | Planned |

---

## Dependencies

### Depends On
| Unit | Reason |
|------|--------|
| — | None. This is the root. |

### Depended By
| Unit | Reason |
|------|--------|
| 002–007 | All of them. Nothing runs without the shell, the DB and the logger. |

### External Dependencies
| System | Purpose | Risk |
|--------|---------|------|
| login-api | PKCE sign-in + JWKS | **High** — hard dependency, no workaround |
| branding-api | theme | Low — default theme fallback |
| auth-api | enrichment | Low — degrade to token claims |
| logs-api | forwarding + usage | Low — `app_logs` is authoritative regardless |
| MySQL | our database | **High** |

---

## Technical Context

### Suggested Technology
Per `standards/tech-stack.md`. Reuse `app-starter/backend/app/security.py` (JWKS cache,
`verify_token`) and `admin.py` (lazy M2M `AdminClient`) **verbatim** — they encode platform
conventions that are easy to get subtly wrong.

### Integration Points
| Integration | Type | Protocol |
|-------------|------|----------|
| login-api | API | OAuth2 PKCE + JWKS over HTTPS |
| branding-api | API | anonymous REST |
| auth-api / logs-api | API | REST via Python admin SDK, M2M bearer |
| MySQL | DB | SQLAlchemy 2.x |

### Data Storage
| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| `app_logs` | SQL | ~50k rows/day at target scale | 30d debug/info, 365d warning+ |
| `user_profiles` | SQL | 1 per user | life of account |

---

## Constraints

- The M2M secret must never be reachable from the browser or appear in any log line.
- `log_event()` is the **only** way anything writes a log. Direct writes to `app_logs` or direct
  `logs.write` calls are a review failure — the two-destination rule has to live in one place.
- Redaction happens before persistence, not before display, and covers request-validation errors
  (a malformed body must not leak a submitted secret into the log store).
- `user_sub` is taken from the validated token. There is no code path where it comes from a request
  body or a query parameter.

---

## Success Criteria

### Functional
- [ ] A user signs in via the embedded form and lands on `/dashboard`
- [ ] Changing project branding changes the app chrome after reload
- [ ] Every request writes exactly one `app_logs` row with `request_id`, status and duration
- [ ] An unhandled exception yields a `critical` row locally **and** in the platform console
- [ ] A feature-usage event is visible in the console's Feature usage view
- [ ] With logs-api stopped, the app still serves every request normally

### Non-Functional
- [ ] Token validation adds < 5ms p95 (JWKS cached, single-flight)
- [ ] Logging adds < 3ms p95 to a request
- [ ] `Authorization` headers and secret-shaped keys never appear in `app_logs`

### Quality
- [ ] Code coverage > 80%
- [ ] All acceptance criteria met
- [ ] Code reviewed and approved

---

## Bolt Suggestions

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| 001-platform-foundation | DDD | 001, 002, 003, 004, 005, 006 | One bolt: the whole floor. Splitting it produces a half-app that cannot be run or tested end to end. |

---

## Notes

**Verify early:** that the JWT `sub` is stable across an email change. Every row in this application
is keyed on it. If it is not stable, this unit changes shape before anything is built on top —
which is exactly why the check belongs here and not in a later unit.

**Do not skip the smoke test.** A missing scope on the M2M role surfaces as a silent 403 inside a
best-effort call that swallows errors by design. Assert all seven scopes at startup in non-prod and
fail loudly.
