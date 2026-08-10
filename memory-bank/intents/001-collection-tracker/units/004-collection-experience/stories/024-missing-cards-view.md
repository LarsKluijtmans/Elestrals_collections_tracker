---
id: 024-missing-cards-view
unit: 004-collection-experience
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 006-collection-browse
implemented: false
---

# Story: 024-missing-cards-view

## User Story

**As a** completionist
**I want** to see what I am missing from a set
**So that** I can take a want-list to a shop or an event

## Acceptance Criteria

- [ ] **Given** I open `/sets/:code` and toggle to missing-only, **Then** only cards I own no printing of appear
- [ ] **Given** a card is missing, **Then** "missing" means no owned printing of that card in the set, at any condition
- [ ] **Given** I export the list, **Then** the CSV is in the format the importer accepts
- [ ] **Given** I compare surfaces, **Then** the missing count and completion percentage agree with the dashboard ring

## Technical Notes

- Definition matters: missing is per *card*, not per *printing*. Owning the common version means the card is not missing, even if you lack the holo.

## Dependencies

### Requires
- 023-set-completion
- 011-set-browser

### Enables
- Wishlist seeding
- Phase 3 want-matching

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Set fully complete | Celebratory empty state, not a blank list |
| Set with no catalog data | States the catalog is incomplete rather than claiming everything is missing |

## Out of Scope

- Buying anything — phase 3
