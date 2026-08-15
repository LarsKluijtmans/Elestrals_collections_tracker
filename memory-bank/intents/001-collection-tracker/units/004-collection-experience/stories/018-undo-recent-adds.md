---
id: 018-undo-recent-adds
unit: 004-collection-experience
intent: 001-collection-tracker
status: ready
priority: should
created: 2026-08-09T12:00:00Z
assigned_bolt: 005-collection-entry
implemented: false
---

# Story: 018-undo-recent-adds

## User Story

**As a** collector entering fast
**I want** to undo a mistaken add
**So that** speed does not cost me accuracy

## Acceptance Criteria

- [ ] **Given** I have added cards this session, **Then** the last 20 adds are individually undoable
- [ ] **Given** I undo an add, **Then** exactly the quantity that add contributed is reversed — not the whole row
- [ ] **Given** the search field is empty, **When** I press `Ctrl/Cmd+Z`, **Then** the last add is undone
- [ ] **Given** an add has since been edited, **When** I undo it, **Then** it is refused with an explanation rather than guessing

## Technical Notes

- Undo reverses a delta, not a row. If a printing was added three times and edited once, undoing the second add must not delete the holding.

## Dependencies

### Requires
- 013-add-inventory-item
- 016-fast-add-flow

### Enables
- Confidence to enter quickly

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Undo after navigating away | Stack is session-scoped and gone; this is stated in the UI |
| Undo of an add whose row was deleted | Refused with a message |
| 21st undo | Oldest entry has aged out; the limit is visible |

## Out of Scope

- A general undo history across sessions
