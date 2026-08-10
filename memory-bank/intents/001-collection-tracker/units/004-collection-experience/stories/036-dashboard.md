---
id: 036-dashboard
unit: 004-collection-experience
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 006-collection-browse
implemented: false
---

# Story: 036-dashboard

## User Story

**As a** collector
**I want** a home page that summarises my collection
**So that** I see progress the moment I sign in

## Acceptance Criteria

- [ ] **Given** I sign in, **Then** four StatTiles show total items, distinct printings, sets started and estimated value
- [ ] **Given** phase 2 has not shipped, **Then** the value tile reads "available in phase 2" — **not** a zero, because a zero is a claim and it is false
- [ ] **Given** I have started sets, **Then** CompletionRings show the three closest to completion
- [ ] **Given** I have made changes, **Then** the last 10 inventory changes list as recent activity
- [ ] **Given** I open the page, **Then** an "add cards" action is prominent
- [ ] **Given** my collection is empty, **Then** I get an onboarding state, not four zeroes

## Technical Notes

- The empty state is the more important of the two designs here — it is what every new user sees first.

## Dependencies

### Requires
- 023-set-completion
- 013-add-inventory-item

### Enables
- Phase 2 replaces the value tile with a real figure

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Exactly one set started | One ring, not three placeholders |
| No recent activity | Section omitted rather than shown empty |
| 10,000 items | Counts come from the summary table, not a live count |

## Out of Scope

- Portfolio value over time — intent 002
