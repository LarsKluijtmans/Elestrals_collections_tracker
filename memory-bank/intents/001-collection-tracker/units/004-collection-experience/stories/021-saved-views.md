---
id: 021-saved-views
unit: 004-collection-experience
intent: 001-collection-tracker
status: ready
priority: should
created: 2026-08-09T12:00:00Z
assigned_bolt: 006-collection-browse
implemented: false
---

# Story: 021-saved-views

## User Story

**As a** collector
**I want** to save a filter set I use often
**So that** I do not rebuild it every session

## Acceptance Criteria

- [ ] **Given** I save a view, **Then** it stores filters, sort and density under a name I choose
- [ ] **Given** views exist, **Then** they list in the filter rail and apply in one click
- [ ] **Given** I no longer want a view, **Then** I can rename or delete it
- [ ] **Given** another user exists, **Then** they never see my views

## Technical Notes

- Stored in a `saved_views` table keyed on `user_sub`, with the filter set as JSON — the same shape the URL serialises.

## Dependencies

### Requires
- 020-collection-filters

### Enables
- Faster repeat sessions

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Saved view references a deleted set | Applies what it can and flags the dropped filter |
| Duplicate view name | Allowed but warned; names are labels, not keys |

## Out of Scope

- Sharing views between users
