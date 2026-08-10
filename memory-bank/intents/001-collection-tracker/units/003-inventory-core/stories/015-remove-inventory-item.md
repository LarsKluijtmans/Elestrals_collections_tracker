---
id: 015-remove-inventory-item
unit: 003-inventory-core
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 004-inventory-core
implemented: false
---

# Story: 015-remove-inventory-item

## User Story

**As a** collector
**I want** to remove cards I no longer own
**So that** my collection stays truthful after I sell or trade

## Acceptance Criteria

- [ ] **Given** quantity is 1, **When** I decrement, **Then** it is a removal and I am asked to confirm
- [ ] **Given** I hold the stepper key down, **Then** it cannot silently delete the row
- [ ] **Given** a removal commits, **Then** completion updates immediately
- [ ] **Given** I target another user's item id, **Then** I get 404 — existence is never confirmed
- [ ] **Given** I bulk-remove a selection, **Then** there is one confirmation for the whole selection, not one per row

## Technical Notes

- Removal is explicit by design. The stepper is used hundreds of times per session and a destructive final step must not be reachable by momentum.

## Dependencies

### Requires
- 013-add-inventory-item

### Enables
- 022-bulk-actions

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Row already removed in another tab | 404 handled as a calm inline message and the row disappears |
| Removal of a holding backing an active listing (phase 3) | Blocked with an explanation — the reservation exists for this reason |

## Out of Scope

- Undo of removals — out of scope; confirmation is the safeguard
