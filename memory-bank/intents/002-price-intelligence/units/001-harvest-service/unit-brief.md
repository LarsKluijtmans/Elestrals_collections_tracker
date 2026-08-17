---
unit: 001-harvest-service
intent: 002-price-intelligence
phase: inception
status: ready
created: '2026-08-15T14:55:00Z'
updated: '2026-08-15T14:55:00Z'
---

# Unit Brief: harvest-service

## Purpose

Stand up the second backend. Everything in this intent that touches an external site runs inside
`harvest-api`, a separately deployable FastAPI service owning the `elestrals_harvest` schema, with
its own Alembic tree, its own MySQL user and its own Celery workers. This unit builds the service,
the schema, the isolation that makes the split real, and the source registry whose gate decides
whether a source may run at all.

The isolation is the point. ADR-004 accepts that scrapers will be blocked, will break when a site
changes, and are acting against some sources' terms. None of that may reach a collector who is
signed in looking at their collection.

## Scope

### In Scope
- `harvest-api` service skeleton: FastAPI app, config, health endpoint, container, compose and
  release wiring
- `elestrals_harvest` schema and its own Alembic tree
- Two MySQL users with non-overlapping write grants, and the read grants each service needs
- Celery + Redis runtime: worker, beat, one queue per source class
- `price_sources` registry with the recorded-risk gate (terms review + named risk owner, both
  enforced by a CHECK constraint)
- `harvest_runs` lifecycle: recorded before work starts, terminal status, crashed-run sweeper
- Per-source token-bucket rate limiting, honest user agent, outbound host allowlist

### Out of Scope
- Any actual connector (unit 002) — this unit ships the frame, not the sources
- Matching, observations, rollups (units 003, 004)
- The admin API and UI (unit 005) — this unit's surfaces are the CLI and the scheduler
- Anything in the `elestrals` schema. This service cannot write it, by grant

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Source registry with a recorded-risk gate | Must |
| FR-13 | The harvester is a second backend | Must |
| FR-2 | Run recording, terminal status and the crashed-run sweeper (the scans themselves are unit 002) | Must |

---

## Domain Concepts

### Key Entities
| Entity | Description | Attributes |
|--------|-------------|------------|
| PriceSource | One place we read from, and the terms we accepted to read it | `key`, `name`, `base_url`, `access_mode`, `enabled`, `tos_review_note`, `risk_accepted_by`, `risk_accepted_on`, `rate_limit_per_min`, `weight`, `reports_sold`, `quarantined_until` |
| HarvestRun | One scan, recorded before it starts | `source_id`, `mode`, `started_at`, `finished_at`, `status`, counters, `error_summary` |

### Key Operations
| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `gate.check(source)` | May this source run right now? | descriptor + config row | pass, or a refusal naming the fix |
| `start_run(source, mode)` | Record the run before any work | source, mode | run id |
| `finish_run(run, status)` | Write counters once, at terminal status | run, counts | run |
| `sweep_stale()` | Fail runs whose process is gone | age threshold | count swept |
| `bucket.acquire()` | Pace one request against the source's limit | tokens | waited seconds |

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
| 001-harvest-service-skeleton | A second deployable backend | Must | Planned |
| 002-harvest-schema-and-grants | Own schema, own user, no write grant on `elestrals` | Must | Planned |
| 003-celery-redis-runtime | Out-of-band work with per-source queues | Must | Planned |
| 004-source-registry-and-risk-gate | A source cannot run without an accepted risk | Must | Planned |
| 005-run-lifecycle-and-sweeper | Every run recorded, no run left `running` | Must | Planned |
| 006-rate-limiting-and-identification | Paced and identifiable on every request | Must | Planned |

---

## Dependencies

### Depends On
| Unit | Reason |
|------|--------|
| intent 001 / 001-platform-foundation | Platform JWT validation, logging conventions, the compose stack this service joins |

### Depended By
| Unit | Reason |
|------|--------|
| 002, 003, 004, 005 | Everything in this intent runs in this service or reads its schema |

### External Dependencies
| System | Purpose | Risk |
|--------|---------|------|
| MySQL (platform instance) | second schema, second user | Low — same instance, new schema; the grants are the only new thing |
| Redis | Celery broker and result backend | Low — new container in the existing compose stack |

---

## Technical Context

### Suggested Technology
FastAPI + SQLAlchemy + Alembic, mirroring `backend/` so the two services read alike. Celery 5 with
Redis as broker; `celery beat` for the schedules. `httpx` for outbound with `follow_redirects=False`
and a per-source token bucket. The service is a sibling directory (`harvest/`) with its own
`Dockerfile`, joining the existing `docker-compose.yml` and the existing release workflow as a
second image.

### Integration Points
| Integration | Type | Protocol |
|-------------|------|----------|
| `elestrals` schema | inbound read | MySQL, read-only grant, cross-schema |
| Redis | broker | TCP |
| logs-api | outbound | HTTPS via the phase-1 logging service |

### Data Storage
| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| `price_sources` | SQL | tens | permanent |
| `harvest_runs` | SQL | ~1k/month | 1 year |

---

## Constraints

- **The grant is the boundary.** `harvest-api`'s MySQL user must hold no write privilege on
  `elestrals`, and the collection backend's user none on `elestrals_harvest`. Verified by a test
  that attempts a write and expects it to be refused — a boundary nobody tests is a comment.
- **A run row exists before any outbound request.** A crash must leave evidence, not silence.
- **Counters are written once, at terminal status.** Incrementing per row lets a crash leave a
  half-counted run that still claims success.
- **The gate raises; it does not return `False`.** A caller who forgets to check a boolean makes a
  request; a caller who forgets to catch an exception makes none.
- Rate limits and quarantine are per-source **data**, changeable without a deploy. That is what
  makes them usable during an incident.
