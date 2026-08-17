---
id: 010-harvest-service-foundation
unit: 001-harvest-service
intent: 002-price-intelligence
type: ddd-construction-bolt
status: complete
stories:
  - 001-harvest-service-skeleton
  - 002-harvest-schema-and-grants
  - 003-celery-redis-runtime
  - 004-source-registry-and-risk-gate
  - 005-run-lifecycle-and-sweeper
  - 006-rate-limiting-and-identification
created: 2026-08-15T15:25:00Z
started: 2026-08-15T15:30:00Z
completed: 2026-08-15T16:20:00Z
current_stage: done
stages_completed: [model, design, implement, test]

requires_bolts:
  - 001-platform-foundation
enables_bolts:
  - 011-scraper-connectors
requires_units: []
blocks: false

complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 1
  testing_scope: 3
---

# Bolt: 010-harvest-service-foundation

## Overview

Stand up `harvest-api` as a second backend with its own schema, its own database user, its own
Alembic tree and its own job runtime — plus the source registry whose gate decides whether anything
may run at all.

## Objective

Make the isolation real before anything starts scraping. At the end of this bolt, a scraper cannot
write phase-1 data even if its code tries, a source cannot run without a written terms review and a
named risk owner, and every run leaves evidence whether it finishes or not.

## Stories Included

- **001-harvest-service-skeleton**: a second deployable backend (Must)
- **002-harvest-schema-and-grants**: own schema, own user, no write grant on `elestrals` (Must)
- **003-celery-redis-runtime**: out-of-band work with per-source queues (Must)
- **004-source-registry-and-risk-gate**: a source cannot run without an accepted risk (Must)
- **005-run-lifecycle-and-sweeper**: every run recorded, no run left `running` (Must)
- **006-rate-limiting-and-identification**: paced and identifiable on every request (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

DDD rather than simple: the gate, the run lifecycle and the source registry are domain rules with
invariants that need modelling before they are coded. Getting the gate wrong is the failure mode
ADR-004 is most exposed to.

## Stages

- [x] **1. model**: Done → ddd-01-domain-model.md
- [x] **2. design**: Done → ddd-02-technical-design.md
- [x] **3. implement**: Done → `harvest/`, migrations, compose and release wiring
- [x] **4. test**: Done → ddd-03-test-report.md, **including the grant tests against real MySQL**

## Dependencies

### Requires
- 001-platform-foundation (JWT validation, logging conventions, the compose stack this joins)

### Enables
- 011-scraper-connectors (and, transitively, everything else in the intent)

## Success Criteria

- [ ] `harvest-api` starts, reports health for MySQL and Redis separately, and joins the release
      workflow as a second image
- [ ] `harvest-api` stopped → `/collection` is unaffected and price surfaces serve last rollups
- [ ] The `harvest-api` user is **refused** on every write to `elestrals`, proven by a test that
      attempts it against real MySQL
- [ ] The `harvest-api` user is refused reading `inventory_items` and `user_profiles`
- [ ] `enabled = 1` with an empty `tos_review_note` or a null `risk_accepted_by` is refused by the
      database, not only by a service method
- [ ] A source off the outbound allowlist cannot run
- [ ] A run row exists before the first outbound request; counters are written once at terminal
      status; a killed process leaves a run that the sweeper resolves to `failed`
- [ ] Rate limiting paces continuously, `Retry-After` is obeyed, off-host redirects are refused
- [ ] An empty `HARVEST_CONTACT_EMAIL` prevents a scan from starting
- [ ] Coverage > 80%

## Notes

The grant tests are the point of this bolt, and they cannot run on SQLite — SQLite has no grants,
so a boundary asserted there asserts nothing. They belong in the MySQL integration suite that
`scripts/verify_mysql.py` already establishes a path for.

Resist sharing a Python package between the two services. Conventions are shared; code is not. A
common package is a coupling that will be regretted the first time one service needs a convention
the other does not want.

robots.txt is deliberately **not** implemented here. ADR-004 decided it is not consulted; story 006
builds everything that was kept, and the omission is recorded in NFR §Conduct rather than left to
be discovered as a gap.

## Construction result - 2026-08-15

**Status: complete.** `harvest/` is a second deployable service with its own schema, Alembic tree,
Dockerfile, Celery worker and beat, joined to the compose stack and the co-locate override.

| Criterion | Verified |
|---|---|
| Starts, health reports MySQL and Redis separately | yes - `app/controllers/health.py`, two fields, not one boolean |
| `harvest-api` stopped leaves `/collection` unaffected | by construction: no call path exists between the services. The only link is a granted read on `price_daily` |
| No write grant on `elestrals`, proven by attempting it | **test written, never run** - `tests/test_grants_mysql.py`, 16 tests, skipped without two narrowly-granted MySQL users. See below |
| `enabled = 1` without a review note **or** a risk owner is refused by the database | yes - `ck_price_sources_risk_accepted_before_enabled`, holds on MySQL and SQLite |
| A source off the outbound allowlist cannot run | yes - `test_harvest_gate.py` |
| Run row exists before the first request; counters written once; sweeper resolves a killed run | yes - `test_harvest_runner.py` |
| Rate limiting paces continuously, obeys `Retry-After`, refuses off-host redirects | yes - `test_harvest_http.py` |
| Empty `HARVEST_CONTACT_EMAIL` prevents a scan | yes - the gate's first check |

**Outstanding: the grant tests have never been executed.** They are the point of this bolt, and
SQLite cannot stand in for them - it has no grants, so a boundary asserted on that path asserts
nothing. `DEPLOY.md` now carries the exact GRANT statements; run

    HARVEST_TEST_MYSQL_URL=... ELESTRALS_TEST_MYSQL_URL=... pytest -m mysql

against the real two-user setup before the first release. Until that passes, FR-13's isolation is
designed and unproven.

**Departure from the plan:** migration 0004 of the old single-backend layout seeded two sources
with pre-written review notes. That is gone. Under ADR-004 a review note records an *accepted risk
with a named person*, and a migration cannot accept a risk on somebody's behalf - so enabling is a
CLI command that requires both `--note` and `--accepted-by`.


## Deployed and proved - 2026-08-17

**The grant tests ran for the first time, and all 16 passed.**

They had been skipped since the bolt was written — `test_grants_mysql.py` needs *both* narrowly
granted MySQL users, and until today neither the `elestrals_harvest` database nor its user existed.
The suite reported "155 tests, 16 skipped" on every run, which is exactly the shape of a boundary
asserted in a document and nowhere else.

Story 002's whole claim is that FR-13's isolation is enforced **by privilege rather than by
convention**. That claim was untested for two days. It is now tested against MySQL 8.4:

| Direction | Result |
|---|---|
| `elestrals_harvest` writing anything in `elestrals` | refused |
| `elestrals_harvest` reading `inventory_items` or `user_profiles` | refused |
| `elestrals_harvest` reading the four catalog tables it needs | allowed |
| `elestrals_app` reading `elestrals_harvest.price_daily` | allowed |
| `elestrals_app` reading `market_listings`, `price_observations`, `harvest_runs`, `price_sources` | refused, all four |

That last row was also checked from *inside the running `elestrals-api` container* rather than only
from a test harness — same result, four `OperationalError`s.

**The deploy found one documentation error.** `GRANT SELECT ON elestrals_harvest.price_daily TO
'elestrals_app'` was listed alongside the other grants, but the table does not exist until the
harvest migration creates it, so running the block as written fails with `ERROR 1146`. `DEPLOY.md`
now splits it out and says why.
