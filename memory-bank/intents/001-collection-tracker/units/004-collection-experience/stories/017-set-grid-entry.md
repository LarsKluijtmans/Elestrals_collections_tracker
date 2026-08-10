---
id: 017-set-grid-entry
unit: 004-collection-experience
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 005-collection-entry
implemented: false
---

# Story: 017-set-grid-entry

## User Story

**As a** collector who just opened a box
**I want** to click through a whole set's grid
**So that** I can record a bulk pull visually instead of typing each name

## Acceptance Criteria

- [ ] **Given** I open `/collection/add/set/:setCode`, **Then** every printing in the set shows as a grid tile
- [ ] **Given** I click a tile, **Then** it is +1; shift-click is −1; neither reloads the page
- [ ] **Given** a tile changes, **Then** its owned-quantity badge updates instantly
- [ ] **Given** I set condition and finish once, **Then** they apply to every click for the session
- [ ] **Given** I am mid-session, **Then** a running total is visible
- [ ] **Given** images are still loading, **Then** tiles hold their aspect ratio and the grid does not reflow

## Technical Notes

- A grid that jumps while you are clicking it is a grid that records the wrong card. Reserve the aspect ratio before art loads.
- Shares the add-session state (carried condition/finish, tally, undo stack) with 016.

## Dependencies

### Requires
- 011-set-browser
- 013-add-inventory-item

### Enables
- Fast bulk entry after a box opening

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Shift-click at quantity 0 | No-op, no error flash |
| Set with 300 printings | Virtualized grid; still 60fps |
| Rapid clicking on one tile | Debounced into a single delta request |

## Out of Scope

- Single-card entry — 016
