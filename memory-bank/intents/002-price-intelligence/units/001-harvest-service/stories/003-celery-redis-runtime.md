---
id: 003-celery-redis-runtime
unit: 001-harvest-service
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 010-harvest-service-foundation
implemented: false
---

# Story: 003-celery-redis-runtime

## User Story

**As an** operator
**I want** scans to run out of band on a real job runtime
**So that** a four-hour deep scan is a background job with retries and isolation, not something
holding an HTTP request open

## Acceptance Criteria

- [ ] **Given** the compose stack, **When** it comes up, **Then** a Redis container, a Celery worker
      and a Celery beat scheduler are running alongside `harvest-api`
- [ ] **Given** a queued scan, **When** the worker picks it up, **Then** it runs to completion
      independently of any HTTP request, and the API process is free throughout
- [ ] **Given** two sources, **When** both are scheduled, **Then** they occupy separate queues so a
      slow or quarantined source does not delay the other
- [ ] **Given** a task that raises, **When** it fails, **Then** it retries with exponential backoff
      up to a configured limit and then ends the run `failed` with the error recorded
- [ ] **Given** the worker is killed mid-task, **When** it restarts, **Then** it does not silently
      re-run a completed scan — the run row is the record of what happened, not the queue
- [ ] **Given** beat, **When** the schedule fires, **Then** the light scan runs on its cadence and
      the deep scan on its own, separately configurable without a deploy

## Technical Notes

Celery 5, Redis as broker and result backend. One queue per **source class** rather than per source,
so adding a source does not add infrastructure: sources are assigned to a class in config.

Beat schedules live in config, not in code, so cadence is an operational decision. Sensible starting
points: light hourly, deep weekly — both well inside the NFR budgets (light < 20 min, deep < 4 h).

Idempotency is owned by the run row and the dedupe keys downstream, **not** by the queue. A task
delivered twice must produce one run's worth of data, and that property comes from
`UNIQUE (source_id, external_id)` on listings and observations rather than from exactly-once
delivery, which Redis does not offer and Celery does not promise.

This replaces the in-process APScheduler phase 1 uses. APScheduler stays in `elestrals-api` for the
phase-1 jobs it already runs; it is not migrated here.

## Dependencies

### Requires
- 001-harvest-service-skeleton

### Enables
- 005-run-lifecycle-and-sweeper
- 008-deep-scan, 009-light-scan
- 027-trigger-and-watch-a-scan

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Redis is down at schedule time | The schedule is missed and logged at `warning`; it is not backfilled — a missed light scan is caught by the next one |
| A task is delivered twice | One run's worth of data, via the downstream dedupe keys. The duplicate run row is visible and ends `success` with 0 new rows |
| Worker killed mid-scan | The run row stays `running` and is swept to `failed` by story 005 |
| Queue backs up behind a slow source | Only that source class is affected; other classes drain normally |
| Beat and a manual trigger collide | Story 027's "refuse a second run of the same source and mode" resolves it |

## Out of Scope

- Autoscaling workers
- Flower or any Celery UI — run visibility is story 026's job, from our own run table
