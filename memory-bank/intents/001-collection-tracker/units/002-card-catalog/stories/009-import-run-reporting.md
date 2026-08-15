---
id: 009-import-run-reporting
unit: 002-card-catalog
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 002-card-catalog-schema-import
implemented: false
---

# Story: 009-import-run-reporting

## Description

Every importer run recorded in `catalog_imports` before work begins, with counts, duration, status and retrievable rejections.

## Rationale

A crashed job must be visible as a run that never finished, not as silence.

## Acceptance Criteria

- [ ] **Given** a run starts, **When** the first fetch happens, **Then** a row already exists with `status = running`
- [ ] **Given** a run ends, **Then** its status is exactly one of `success | partial | failed`
- [ ] **Given** a run completes, **Then** counts are recorded for seen, added, updated and rejected
- [ ] **Given** rows were rejected, **When** I query the run, **Then** each rejection carries the source record identity and a human-readable reason
- [ ] **Given** a source fails mid-run, **Then** the run is marked `partial` and the catalog is left consistent
- [ ] **Given** a process crashes, **When** the sweeper runs, **Then** a stale `running` row past its timeout becomes `failed`

## Technical Notes

- Insert-before-work is the whole point. A row written only on success cannot distinguish "never ran" from "died halfway".

## Dependencies

### Requires
- 007-catalog-schema

### Enables
- 034-admin-catalog-console

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Two runs start concurrently for one source | Advisory lock; the second exits immediately as skipped |
| Run succeeds with zero records | `success` with counts of zero, and a warning — silence and emptiness are different |

## Out of Scope

- The operator UI — 034
