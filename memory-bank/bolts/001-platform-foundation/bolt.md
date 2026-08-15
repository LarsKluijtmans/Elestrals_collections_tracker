---
id: 001-platform-foundation
unit: 001-platform-foundation
intent: 001-collection-tracker
type: simple-construction-bolt
status: in-progress
stories:
  - 001-sign-in-with-platform
  - 002-app-shell-and-routing
  - 003-branding-driven-theme
  - 004-app-logging
  - 005-platform-log-forwarding
  - 006-usage-metering
created: 2026-08-09T12:00:00Z
started: null
completed: null
current_stage: null
stages_completed: []

requires_bolts: []
enables_bolts:
  - 002-card-catalog-schema-import
requires_units: []
blocks: false

complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 0
  testing_scope: 2
---

# Bolt: 001-platform-foundation

## Overview

Fork `../app-starter` into this repository, stand up the `elestrals` database, and wire every
cross-cutting concern: sign-in, branding, our own logging with platform forwarding, and usage
metering.

## Objective

Reach a running, signed-in, themed, observable application with an empty domain. Every subsequent
bolt starts from working rather than blank.

## Stories Included

- **001-sign-in-with-platform**: PKCE via embedded `<LoginForm>` (Must)
- **002-app-shell-and-routing**: rail, top bar, routing, EN/NL, error boundary (Must)
- **003-branding-driven-theme**: whole-app theme from branding-api (Must)
- **004-app-logging**: `app_logs` + `log_event()` with redaction (Must)
- **005-platform-log-forwarding**: errors and security events to logs-api (Must)
- **006-usage-metering**: `usage_track()` to logs-api (Must)

## Bolt Type

**Type**: Simple Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/simple-construction-bolt.md`

**Retyped from `ddd-construction-bolt` at construction start.** This bolt is scaffolding and
wiring — fork a starter, create a database, install a logging helper. Its four entities (Principal,
UserProfile, AppLogEntry, UsageEvent) are already enumerated in the unit brief and have no
invariants worth modelling. A five-stage DDD cycle here produces ceremony, not insight. The DDD
bolts start at 002, where the domain actually begins.

## Stages

- ✅ **1. plan**: Complete → `implementation-plan.md`
- ✅ **2. implement**: Complete → `frontend/`, `backend/`
- ⏳ **3. test**: Partial → `test-report.md` ← current

All six stories implemented. 10 backend tests pass; frontend typechecks and builds clean.
Nine acceptance criteria remain unverified because they need a **running platform** — sign-in,
both blocking checks, the branding round-trip, `app_logs` rows, console visibility and the
logs-api-down path. See the test report. The bolt closes when those are exercised.

## Dependencies

### Requires
- None. This is the first bolt.

### Enables
- 002-card-catalog-schema-import, and transitively everything else

## Success Criteria

- [ ] Sign in, land on `/dashboard`, sign out
- [ ] Changing project branding changes the app chrome after reload
- [ ] One `app_logs` row per request; unhandled exceptions produce a `critical` row with a trace
- [ ] Errors visible in the platform console; a feature-usage event visible in the console
- [ ] With logs-api stopped, every request still succeeds
- [ ] All seven M2M scopes asserted at startup in non-prod
- [ ] Coverage > 80%

## Notes

**Two blocking checks belong here, at the very start:**

1. **Is the JWT `sub` stable across an email change?** Every row we own is keyed on it. If it is
   not, this bolt changes shape before anything is built on top.
2. **Can the M2M service account be provisioned with all seven scopes?** A missing scope surfaces
   later as a silent 403 inside a call that swallows errors by design. Assert loudly at startup.

Do not begin bolt 002 until both are answered.
