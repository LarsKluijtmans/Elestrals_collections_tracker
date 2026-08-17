---
id: 006-scan-schema-and-grants
unit: 002-scan-service
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T13:41:00Z'
assigned_bolt: 019-scan-service-foundation
implemented: false
---

# Story: 006-scan-schema-and-grants

## User Story

**As** the person who has to trust three services with one database
**I want** the boundary between them enforced by database privileges rather than by code review
**So that** a mistake surfaces as a permission error in development instead of as a corrupted table in
production

## Acceptance Criteria

- [ ] **Given** the MySQL instance, **When** migrations run, **Then** `elestrals_scan` exists with its
      **own** Alembic tree, and neither existing tree is touched
- [ ] **Given** `scan-api`'s MySQL user, **When** it attempts any write to `elestrals`, **Then** the
      database refuses it — verified by a test that performs the write and expects the refusal
- [ ] **Given** `scan-api`'s MySQL user, **When** it attempts any write to `elestrals_harvest`,
      **Then** the database refuses it the same way
- [ ] **Given** the collection backend's user, **When** it attempts a write to `elestrals_scan`,
      **Then** the database refuses it
- [ ] **Given** `scan-api`, **When** it reads `sets`, `cards` and `printings`, **Then** it succeeds —
      the read grant is real and scoped to those tables
- [ ] **Given** the collection backend, **When** it reads `elestrals_scan`, **Then** it can read
      `printing_display_images` and **nothing else**
- [ ] **Given** the grants, **When** they are reviewed, **Then** they are declared in the deployment
      configuration alongside intent 002's, not applied by hand to one machine

## Technical Notes

Third schema, third user, same pattern as `elestrals_harvest`. The grant matrix:

| User | `elestrals` | `elestrals_harvest` | `elestrals_scan` |
|---|---|---|---|
| `elestrals_app` | ALL | SELECT on `price_daily` | SELECT on `printing_display_images` |
| `elestrals_harvest_app` | SELECT on catalog | ALL | — |
| `elestrals_scan_app` | SELECT on catalog | — | ALL |

The negative tests matter more than the positive ones. A read grant that is missing announces itself
the first time the feature runs; a write grant that was accidentally given announces itself never,
until the day it is used.

`printing_display_images` is deliberately the only table the collection backend may read, mirroring
`price_daily`'s role in intent 002. It is a published table rather than a view, so the read path stays
a single-table select that cannot reach a private column by joining.

## Dependencies

### Requires
- 005-scan-api-skeleton

### Enables
- 007-capture-store
- 023-published-image-projection

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Local development uses a permissive root user | The grant tests must run against a properly restricted user, or they prove nothing. This is how a boundary silently stops existing |
| A migration in one tree needs a table from another | It does not get one. Cross-schema reads are runtime reads with a grant, never migration-time dependencies |
| The projection table needs a new column | Additive only, and the collection backend's read is explicit about columns so a new one cannot leak into a response by surprise |

## Out of Scope

- The tables themselves beyond their existence (stories 007, 009, 023)
- Any data
