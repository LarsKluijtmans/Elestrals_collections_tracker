---
id: 022-bulk-actions
unit: 004-collection-experience
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 006-collection-browse
implemented: false
---

# Story: 022-bulk-actions

## User Story

**As a** collector
**I want** to act on many rows at once
**So that** selling 200 cards is not 200 interactions

## Acceptance Criteria

- [ ] **Given** I select-all, **Then** it respects the active filter and says how many rows that is
- [ ] **Given** a selection exists, **Then** I can bulk-edit condition, location and for-trade
- [ ] **Given** I bulk-delete, **Then** there is a single confirmation naming the count
- [ ] **Given** a selection exists, **Then** I can export just that selection
- [ ] **Given** part of a bulk operation fails, **Then** the report names exactly which rows failed and why, and the rest are applied

## Technical Notes

- Partial success must be reported honestly. An all-or-nothing bulk edit over 500 rows fails the whole operation for one bad row; a silent partial leaves the user not knowing what happened.

## Dependencies

### Requires
- 019-collection-table
- 020-collection-filters
- 014-edit-inventory-item

### Enables
- Realistic collection maintenance

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Select-all over 10,000 rows | Selection is the filter, not 10,000 ids |
| Bulk delete of everything | Confirmation requires typing the count |
| Row changes between selection and action | That row fails and is named; others proceed |

## Out of Scope

- Bulk operations on sealed or wishlist
