---
unit: 004-collection-experience
intent: 001-collection-tracker
phase: inception
status: stories-defined
created: '2026-08-09T12:00:00Z'
updated: '2026-08-09T12:00:00Z'
---

# Unit Brief: collection-experience

## Purpose

Everything the collector actually touches: the dashboard, the collection table, and the two entry
flows. This unit carries the highest UX risk in the intent — the product is judged almost entirely
on how it feels to enter 400 cards and then find one of them again.

## Scope

### In Scope
- `/dashboard` — stat tiles, completion rings, recent activity
- `/collection` — virtualized table, filter rail, sorting, density toggle, saved views, bulk actions
- `/collection/add` — keyboard-first single-add flow with carry-forward and session tally
- `/collection/add/set/:setCode` — whole-set grid entry
- Undo for recent adds
- `/sets/:code` missing-cards view
- The optimistic mutation layer with visible revert

### Out of Scope
- The inventory write model (unit 003)
- Sealed and wishlist surfaces (unit 005)
- CSV (unit 006)
- Prices anywhere on these pages (intent 002 adds the columns)

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-8 | Fast bulk entry | Must |
| FR-9 | Browse and filter the collection | Must |
| FR-10 | Set completion (the UI half) | Must |

---

## Domain Concepts

### Key Entities
| Entity | Description | Attributes |
|--------|-------------|------------|
| SavedView | A named filter+sort+density preset | `user_sub`, `name`, `filters`, `sort`, `density` |
| AddSession | Ephemeral client state during bulk entry | carried condition/finish, tally, undo stack |

### Key Operations
| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `quickAdd` | Search → select → save → refocus | query, carried defaults | optimistic row + tally entry |
| `undoAdd` | Reverse one of the last 20 adds | add id | reverted row |
| `applyView` | Restore a saved filter set | view id | table state |
| `bulkMutate` | Edit/delete/export a selection | selection, action | result summary |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 9 |
| Must Have | 7 |
| Should Have | 2 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 016-fast-add-flow | Keyboard-first card entry | Must | Planned |
| 017-set-grid-entry | Enter a whole set from a grid | Must | Planned |
| 018-undo-recent-adds | Undo a mistaken add | Should | Planned |
| 019-collection-table | Virtualized collection table | Must | Planned |
| 020-collection-filters | Combine filters | Must | Planned |
| 021-saved-views | Save and restore a view | Should | Planned |
| 022-bulk-actions | Act on a selection | Must | Planned |
| 024-missing-cards-view | See what I am missing | Must | Planned |
| 036-dashboard | Collection dashboard | Must | Planned |

---

## Dependencies

### Depends On
| Unit | Reason |
|------|--------|
| 002-card-catalog | Search, sets, printings |
| 003-inventory-core | Every read and write on this surface |

### Depended By
| Unit | Reason |
|------|--------|
| — | Nothing. This is a leaf. |

### External Dependencies
| System | Purpose | Risk |
|--------|---------|------|
| branding-api | theme tokens | Low |

---

## Technical Context

### Suggested Technology
TanStack Table + TanStack Virtual for the row list; TanStack Query mutations with
`onMutate`/`onError` rollback for optimism; React Hook Form + Zod in the add flow. Filters are
serialised into the URL so a view is shareable and the back button behaves.

### Integration Points
| Integration | Type | Protocol |
|-------------|------|----------|
| Our API | REST | `/api/v1/inventory`, `/api/v1/cards`, `/api/v1/completion` |

### Data Storage
| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| `saved_views` | SQL | a handful per user | life of account |
| Add-session state | client memory | ephemeral | discarded on navigation |

---

## Constraints

- **The add flow is keyboard-complete.** Type → arrow → `Enter` saves, clears and refocuses. Mouse
  use is optional at every step. This is the single accessibility requirement that is also the
  single most important performance requirement.
- Condition and finish carry forward between adds; a box of cards is usually uniform and re-picking
  them 400 times is the difference between a usable product and an abandoned one.
- Optimistic updates must revert **visibly** — a silent revert teaches users not to trust the UI.
- The table must not reflow when images load: skeletons hold the exact final aspect ratio.
- Element chips are tinted, never solid (see `ux-guide.md` §3) and always carry the element name.
- Respect `prefers-reduced-motion` for the foil sheen and chart entry.

---

## Success Criteria

### Functional
- [ ] 100 cards entered in under 10 minutes by a first-time user, measured
- [ ] Median single-add interaction under 5 seconds, keyboard only
- [ ] Grid mode: click +1, shift-click −1, no reload, running total visible
- [ ] Filters combine and survive a page reload via the URL
- [ ] A saved view restores filters, sort and density
- [ ] Bulk-select 500 rows and delete them in one action with one confirmation

### Non-Functional
- [ ] 10,000 rows scroll at 60fps on a mid-range laptop
- [ ] Table interactive within 1.5s p75 on a warm cache
- [ ] Full keyboard path through add, filter and bulk-edit, verified with a screen reader
- [ ] WCAG 2.2 AA on every page in this unit

### Quality
- [ ] Component tests for the add flow's keyboard contract
- [ ] Code coverage > 80%
- [ ] Code reviewed and approved

---

## Bolt Suggestions

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| 005-collection-entry | DDD | 016, 017, 018 | The two entry flows and undo — build and measure these first, they carry the risk |
| 006-collection-browse | DDD | 019, 020, 021, 022, 024, 036 | Table, filters, views, bulk actions, missing view, dashboard |

---

## Notes

Entry is bolted **before** browsing on purpose. Browsing an empty collection tells you nothing; the
moment entry works, there is real data to browse, and the timing target (100 cards / 10 minutes) can
be measured with a real person instead of estimated.

If the 5-second median is missed, the fix is in the interaction, not the infrastructure — fewer
required fields, better defaults, more aggressive carry-forward. Do not respond to a slow add flow
by optimising the API that is already answering in 200ms.
