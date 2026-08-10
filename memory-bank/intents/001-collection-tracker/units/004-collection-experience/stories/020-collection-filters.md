---
id: 020-collection-filters
unit: 004-collection-experience
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 006-collection-browse
implemented: false
---

# Story: 020-collection-filters

## User Story

**As a** collector
**I want** to narrow my collection by any attribute
**So that** I can answer questions like "which Fire holos do I have in NM"

## Acceptance Criteria

- [ ] **Given** I open the filter rail, **Then** I can filter on set, element, rarity, condition, finish, language, graded and for-trade
- [ ] **Given** I select several values, **Then** they combine with AND across attributes and OR within an attribute
- [ ] **Given** filters are active, **Then** they are serialised into the URL, so the view is shareable and the back button works
- [ ] **Given** any filter is active, **Then** a result count is always visible
- [ ] **Given** I want to start over, **Then** clearing all filters is one action

## Technical Notes

- URL serialisation is what makes a filtered view a shareable artifact and makes the back button behave. Retrofitting it later means rewriting every filter component.

## Dependencies

### Requires
- 019-collection-table

### Enables
- 021-saved-views
- 022-bulk-actions
- 027-csv-export

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Filter combination matching nothing | Empty state naming the filters, with a clear-all action |
| Very long URL from many filters | Compressed encoding above a threshold |
| Filter on a set the user owns nothing from | Allowed; returns empty |

## Out of Scope

- Saving a filter set — 021
