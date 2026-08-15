---
id: 026-wishlist
unit: 005-sealed-and-wishlist
intent: 001-collection-tracker
status: ready
priority: should
created: 2026-08-09T12:00:00Z
assigned_bolt: 007-sealed-and-wishlist
implemented: false
---

# Story: 026-wishlist

## User Story

**As a** collector
**I want** a list of cards I am hunting
**So that** I know what to look for and what I am willing to pay

## Acceptance Criteria

- [ ] **Given** I add a printing, **Then** I can set a desired quantity, an optional maximum price and a priority
- [ ] **Given** a printing is already wished, **Then** it cannot be added twice
- [ ] **Given** I add a wished printing to inventory, **Then** I am prompted to clear the wish — and it clears only on confirmation
- [ ] **Given** I export, **Then** the wishlist is included
- [ ] **Given** I view an entry, **Then** it links to the card detail page

## Technical Notes

- Do not auto-clear on acquisition. A collector may want a second copy, or a better condition, and silently removing the wish loses that intent.
- These entries are the seed for phase-2 price alerts; the schema anticipates that without building it.

## Dependencies

### Requires
- 007-catalog-schema

### Enables
- Phase 2 price alerts
- Phase 3 want-matching

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Max price with no currency | Rejected — a bare number is not money |
| Wishing a printing already owned | Allowed; wanting a second copy is legitimate |

## Out of Scope

- Alerts — intent 002
