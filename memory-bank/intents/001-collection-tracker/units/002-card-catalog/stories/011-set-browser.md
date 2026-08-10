---
id: 011-set-browser
unit: 002-card-catalog
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 003-card-catalog-surface
implemented: false
---

# Story: 011-set-browser

## User Story

**As a** collector
**I want** to browse sets and see a full checklist
**So that** I can work through a set systematically

## Acceptance Criteria

- [ ] **Given** I open `/sets`, **Then** every set lists with name, code, release date and printed card count
- [ ] **Given** I am signed in, **Then** each set shows a CompletionRing; signed out, it does not
- [ ] **Given** I open `/sets/:code`, **Then** every printing lists in collector-number order
- [ ] **Given** I am signed in, **When** I toggle, **Then** I can view owned / missing / all; signed out shows all
- [ ] **Given** I want a want-list, **When** I export missing, **Then** I get a CSV the importer accepts

## Technical Notes

- Ring stroke takes the set's dominant element hue over a grey track.
- Build the ring with a null state here so the page is complete before completion data exists (bolt 004).

## Dependencies

### Requires
- 008-catalog-importer

### Enables
- 024-missing-cards-view
- 023-set-completion (renders here)

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Set with no cards imported yet | Shows the printed count with a "catalog incomplete" notice rather than 0% |
| Set with more printings than the printed count | Alt arts and promos exist; completion uses distinct cards, not printings, as the denominator |

## Out of Scope

- The completion calculation itself — 023
