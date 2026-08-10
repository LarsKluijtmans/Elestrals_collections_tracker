---
id: 006-usage-metering
unit: 001-platform-foundation
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 001-platform-foundation
implemented: false
---

# Story: 006-usage-metering

## Description

A `usage_track()` helper recording feature usage to logs-api's feature-usage stream.

## Rationale

The platform already has a metering surface and a console view for it. Building our own analytics would duplicate it for no gain.

## Acceptance Criteria

- [ ] **Given** inventory is added, **When** the write commits, **Then** `inventory.item_added` records with the user as subject, the quantity added, and the set code as `reference_1`
- [ ] **Given** events have been recorded, **When** I open the console's Feature usage view, **Then** the counts appear and group by `reference_1`
- [ ] **Given** metering fails, **When** the request completes, **Then** the request still succeeds
- [ ] **Given** a new feature key is needed, **When** it is added, **Then** it is declared in one module so the vocabulary cannot drift

## Technical Notes

- Scope required: `usage:write`. Feature keys are listed in `standards/system-architecture.md`.
- `feature` is any string — no schema change is needed to add one, which is exactly why the key list must be centralised or it will sprawl.

## Dependencies

### Requires
- 004-app-logging

### Enables
- Product usage reporting from day one

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Quantity zero | Not recorded; a zero-quantity event is noise |
| Very high cardinality reference | Bounded length, truncated with a marker |

## Out of Scope

- Reading usage back — the platform console does this
