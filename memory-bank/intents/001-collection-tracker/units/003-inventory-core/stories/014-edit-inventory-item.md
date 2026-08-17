---
id: 014-edit-inventory-item
unit: 003-inventory-core
intent: 001-collection-tracker
status: complete
priority: must
created: '2026-08-09T12:00:00Z'
assigned_bolt: 004-inventory-core
implemented: true
---

# Story: 014-edit-inventory-item

## User Story

**As a** collector
**I want** to correct a holding after I recorded it
**So that** mistakes are cheap and I keep the data accurate

## Acceptance Criteria

- [ ] **Given** I open a holding, **Then** quantity, condition, grading, cost basis, date, location, notes and for-trade are all editable
- [ ] **Given** I change a condition to one I already hold, **Then** the two rows merge and their quantities sum
- [ ] **Given** a merge is about to happen, **Then** I am asked to confirm, because a second edit cannot undo it
- [ ] **Given** an edit changes distinct printings owned, **Then** completion recomputes
- [ ] **Given** an edit fails on the server, **Then** the optimistic change reverts **visibly**
- [ ] **Given** I edit another user's item id, **Then** I get 404

## Technical Notes

- The merge case is the subtle one: editing condition can collide with an existing row, and silently discarding one of them loses data the user entered.

## Dependencies

### Requires
- 013-add-inventory-item

### Enables
- 022-bulk-actions

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Edit to a condition that collides with a graded row | No merge — graded copies stay separate |
| Concurrent edit from two tabs | Last write wins on metadata; quantity uses a delta, not an absolute |
| Cost basis cleared | Allowed; phase-2 P/L treats it as unknown, never as zero |

## Out of Scope

- Bulk editing — 022
