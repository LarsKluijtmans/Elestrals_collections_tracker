---
id: 027-trigger-and-watch-a-scan
unit: 005-admin-console
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 013-admin-console-core
implemented: false
---

# Story: 027-trigger-and-watch-a-scan

## User Story

**As an** admin
**I want** to start either scraper from the dashboard and watch it work
**So that** running a scan does not require a shell on the server

## Acceptance Criteria

- [ ] **Given** an enabled, non-quarantined source, **When** I trigger a deep or light scan, **Then**
      the request returns immediately with a run id rather than blocking
- [ ] **Given** a triggered scan, **When** I watch it, **Then** counters update while it runs and the
      status resolves to `success`, `partial` or `failed` when it ends
- [ ] **Given** a scan already running for a source and mode, **When** I trigger the same again,
      **Then** it is **refused** with a clear message, not silently queued
- [ ] **Given** a running scan, **When** I stop it, **Then** it ends `partial` with the data it had
      gathered, and the run says it was stopped by an admin
- [ ] **Given** a quarantined or disabled source, **When** I try to trigger it, **Then** it is
      refused with the reason and, for quarantine, when it will next be retried
- [ ] **Given** a scan triggered from the dashboard, **When** it runs, **Then** it executes the same
      code as the scheduled scan — one execution path, not two
- [ ] **Given** any trigger, **When** it is made, **Then** it requires the admin scope like every
      other admin route
- [ ] **Given** the browser is closed mid-scan, **When** the admin returns, **Then** the run is still
      progressing or finished — nothing about the scan depends on the page staying open

## Technical Notes

`202 Accepted` with a run id, matching the phase-1 admin import endpoint. The run row is created
synchronously so the id is real before the response returns; the work is queued to Celery.

Refusing a duplicate rather than queueing it: silently queueing makes an admin press the button
twice and wonder why nothing happened, and then get two runs an hour apart. The refusal is a `409`.

Stopping sets a flag the scan checks between queries, so it stops at a clean boundary and finishes
its run row properly. Killing the worker would leave a `running` row for the sweeper, which works
but reports the wrong cause.

Live counters poll the run-detail endpoint. One admin watching one run does not justify a websocket,
and polling degrades gracefully when `harvest-api` is briefly unreachable.

## Dependencies

### Requires
- 026-run-history-and-health
- 003-celery-redis-runtime, 005-run-lifecycle-and-sweeper
- 008-deep-scan, 009-light-scan

### Enables
- Nothing downstream. This is the story that makes the console operable rather than observational

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Redis is down | Trigger returns an error saying work cannot be queued; no run row is left `running` |
| Scan is stopped before it fetched anything | Ends `partial` with zero counters and the stop reason |
| Two admins trigger simultaneously | One wins, one gets the `409` |
| A scheduled run is already going when an admin triggers | Same `409`. The scheduler has no priority over a human, and vice versa |
| The scan finishes between two polls | The final status is what the poll returns; no event is missed because the run row is the source of truth, not a stream |

## Out of Scope

- Scheduling changes from the UI — cadence is configuration
- Running a scan against a source that has not cleared the gate. There is no override
