---
id: 006-collection-browse
unit: 004-collection-experience
intent: 001-collection-tracker
type: ddd-construction-bolt
status: partial
stories:
  - 019-collection-table
  - 020-collection-filters
  - 021-saved-views
  - 022-bulk-actions
  - 024-missing-cards-view
  - 036-dashboard
created: 2026-08-09T12:00:00Z
started: 2026-08-17T19:10:00Z
completed: null
current_stage: done
stages_completed:
  - name: model
    completed: 2026-08-17T19:20:00Z
    artifact: FilterSet, keyset cursors, collection_snapshots, saved_views
  - name: design
    completed: 2026-08-17T19:30:00Z
    artifact: 0004_browse.py, 9 endpoints, 6 services
  - name: implement
    completed: 2026-08-17T20:00:00Z
    artifact: backend/app/controllers/collection.py, frontend/src/collection/
  - name: test
    completed: 2026-08-17T20:10:00Z
    artifact: ddd-03-test-report.md

requires_bolts:
  - 005-collection-entry
enables_bolts: []
requires_units: []
blocks: false

complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: 006-collection-browse

## Overview

The collection table with filters, saved views and bulk actions; the missing-cards view; and the
dashboard. This is the bolt where the product becomes something worth showing another person.

## Objective

Ten thousand holdings, browsable at 60fps, filterable along every attribute that matters, with bulk
operations that make selling 200 cards one interaction rather than 200.

## Stories Included

- **019-collection-table**: virtualized table (Must)
- **020-collection-filters**: combining filters, serialised into the URL (Must)
- **021-saved-views**: named presets (Should)
- **022-bulk-actions**: bulk edit, delete, export (Must)
- **024-missing-cards-view**: what I am missing from a set (Must)
- **036-dashboard**: stat tiles, completion rings, recent activity (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. model**: Done → `FilterSet` (the vocabulary story 033 reuses), keyset cursors,
      `collection_snapshots`, `saved_views`
- [x] **2. design**: Done → `0004_browse.py`, nine endpoints, six services
- [x] **3. implement**: Done → `backend/app/controllers/collection.py`, `frontend/src/collection/`
- [x] **4. test**: Done → ddd-03-test-report.md — 135 new tests, 95% on this bolt's modules

## Dependencies

### Requires
- 005-collection-entry (real data to browse)

### Enables
- Nothing in this intent. Intent 002 attaches its value and delta columns to this table.

## Success Criteria

- [~] 10,000 rows at 60fps on a mid-range laptop; list API p95 < 400ms — **the API half is
      measured and met**, at 10,000 real holdings on MySQL 8.4 (2026-08-17): 23.7ms unfiltered,
      36.3ms filtered, and 23.2ms a thousand pages deep. The 60fps scroll still needs a browser
      and a profiler, and no test suite can produce that number
- [x] Cursor pagination, not offset — **keyset**, and pinned by a test that inserts a row
      mid-page and proves the window does not shift
- [x] Filters combine, serialise to the URL, and survive reload and the back button
- [x] Saved view restores filters, sort and density
- [x] Bulk delete of 500 rows: one confirmation naming the count — and above 20 rows the count
      has to be **typed**
- [x] Partial bulk failure reports which rows failed and applies the rest
- [x] Missing count and completion agree with the dashboard ring — asserted across both surfaces
      in one test, because that is where they would silently diverge
- [x] Empty and onboarding states written before the components
- [~] Full keyboard path, verified with a screen reader; WCAG 2.2 AA — the semantics are in place
      and asserted (`aria-sort`, `aria-pressed`, named controls, live counts); **an actual screen
      reader and an axe pass are not**, same gap bolt 003 carries
- [x] Coverage > 80% — 95% on this bolt's backend modules

## Notes

Build the table with the phase-2 columns in mind but **do not stub them with zeroes**. The dashboard
value tile says "available in phase 2" rather than showing €0 — a zero is a claim, and it is a false
one.

Row height must be fixed per density mode. Variable-height virtualization is the usual cause of
stutter in tables like this, and it is much harder to remove later than to avoid now.

## Construction result - 2026-08-17

**Status: partial.** All six stories built; the bolt stays `partial` on two measurements and one
audit, not on a story.

| Story | State |
|---|---|
| 019 collection table | done — virtualized, fixed row height per density, optimistic stepper with visible revert |
| 020 collection filters | done — AND across attributes, OR within, serialised to the URL both ways |
| 021 saved views | done — stores the *same shape* the URL serialises, so a view and a shared link cannot drift |
| 022 bulk actions | done — selection is a filter, partial success named row by row |
| 024 missing cards view | done — per *card*, and pinned to agree with the dashboard ring |
| 036 dashboard | done — and the value tile still refuses to render a zero |

**`collection_snapshots` shipped with this bolt** rather than with the story that needs it. It was
phase-1 work, planned a year early as insurance so phase 2's portfolio chart would not start empty,
and left unbuilt long enough that intent 002's stories 021, 022 and 032 were all recorded `blocked`
on it — the exact outcome planning it early existed to avoid. It is written nightly by
`python -m app.jobs --snapshot`, and its `total_value_cents` is **nullable on purpose**: phase 1
counts, phase 2 values, and a zero would be a claim.

**The decision worth keeping.** Paging is keyset, not offset, and `core/pagination.py` had already
reserved the spot: *"when a query without a total order needs paging, it needs a keyset cursor
instead — and this is the one place to add it."* The collection is that query. A collector adds cards
while scrolling, so an offset silently repeats or skips rows, and neither failure looks like an
error — it looks like the table lost a card.

**The bug worth recording.** The quantity stepper wrote back a burst that netted to zero: click `+`,
correct the mis-click with `−`, and the debounce fired "set it to what it already is". The fix
compares against the *server's* value rather than the last displayed one — which is the rule the
grid's delta coalescer already applied to a click-then-shift-click, arrived at independently a second
time in the same product. Worth noticing as a pattern rather than as two bugs.

Also: three controllers built response models with `vars()` on `slots=True` dataclasses, which have
no `__dict__`. Five API tests failed at once and named it immediately.
