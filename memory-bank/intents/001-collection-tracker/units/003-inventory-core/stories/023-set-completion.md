---
id: 023-set-completion
unit: 003-inventory-core
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 004-inventory-core
implemented: false
---

# Story: 023-set-completion

## User Story

**As a** completionist
**I want** to see how much of each set I own
**So that** I know what to chase next

## Acceptance Criteria

- [ ] **Given** I own cards in a set, **Then** completion is `distinct owned printings in set / sets.card_count`
- [ ] **Given** an inventory write commits, **Then** completion was recomputed inside the same transaction
- [ ] **Given** a page reads completion, **Then** it reads the summary table — never a live aggregate
- [ ] **Given** I own sealed product, **Then** it is excluded from the calculation entirely
- [ ] **Given** the projection is suspect, **When** I run the rebuild command, **Then** it regenerates wholly from inventory
- [ ] **Given** a write happens, **Then** recompute adds under 50ms p95

## Technical Notes

- A summary table that can drift from its source is worse than no summary table. Recompute is transactional: if it fails, the write rolls back.
- Only sets touched by the write are recomputed, not every set the user owns.

## Dependencies

### Requires
- 013-add-inventory-item
- 007-catalog-schema

### Enables
- 011-set-browser
- 024-missing-cards-view
- 036-dashboard

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| `card_count` is 0 or null | Completion is undefined, shown as "—", never as a division error |
| User owns a printing not counted in the printed set size | Completion caps at 100% |
| Bulk import of 3,000 rows | Recompute runs once per affected set at the end, not per row |

## Out of Scope

- Rendering rings — 011 and 036
