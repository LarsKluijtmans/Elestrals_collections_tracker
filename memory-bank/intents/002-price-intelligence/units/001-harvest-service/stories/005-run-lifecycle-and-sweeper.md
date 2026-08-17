---
id: 005-run-lifecycle-and-sweeper
unit: 001-harvest-service
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 010-harvest-service-foundation
implemented: false
---

# Story: 005-run-lifecycle-and-sweeper

## User Story

**As an** admin
**I want** every scan recorded before it starts and resolved when it ends, however it ends
**So that** "did last night's scan finish?" is a question the database can answer

## Acceptance Criteria

- [ ] **Given** a scan is about to start, **When** it begins, **Then** a `harvest_runs` row exists
      *before* the first outbound request, carrying source, mode and start time
- [ ] **Given** a scan completes, **When** it finishes, **Then** its counters are written **once**,
      at terminal status, and the status is one of `success`, `partial`, `failed`
- [ ] **Given** a scan where some queries failed and some succeeded, **When** it ends, **Then** the
      status is `partial` and `error_summary` names the failures
- [ ] **Given** a scan where nothing was fetched and something failed, **When** it ends, **Then** the
      status is `failed`
- [ ] **Given** a run left `running` past the stale threshold, **When** the sweeper runs, **Then** it
      is set `failed` with an explanation that the owning process is gone
- [ ] **Given** the process is killed mid-scan, **When** it is restarted, **Then** no run remains
      `running` indefinitely and the console never shows a scan in progress that is not

## Technical Notes

Counters written once at terminal status, not incremented per row — the same rule
`catalog_imports` follows in phase 1, and for the same reason: a crash must not leave a
half-counted run that still claims success.

Counters: `queries`, `fetched`, `parsed`, `accepted`, `rejected`, `discovered`, `ended`.
`parsed - accepted` is the number story 028 trends as match quality, so it has to be a real count
and not an estimate.

The stale threshold is configuration, defaulting comfortably above the 4-hour deep-scan budget so a
slow run is not declared dead while it is still working.

The sweeper is a beat job, and it also runs at service startup — a deploy is the most common moment
for a run to have been orphaned.

## Dependencies

### Requires
- 003-celery-redis-runtime

### Enables
- 008-deep-scan, 009-light-scan
- 026-run-history-and-health
- 027-trigger-and-watch-a-scan

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Run crashes before any request | Row exists, `running`, swept to `failed`. Evidence, not silence |
| Run is stopped by an admin | Ends `partial` with what it had (story 027) |
| Sweeper runs while a legitimate long scan is going | Threshold is above the NFR budget; a scan exceeding it is a bug worth surfacing |
| Two sweepers run concurrently | Idempotent — setting `failed` twice is the same as once |
| Clock skew between API and worker | All timestamps are UTC from the database's perspective where it matters; the threshold is generous enough to absorb skew |

## Out of Scope

- Displaying any of this (story 026)
- Retry policy for the scan itself (story 003)
