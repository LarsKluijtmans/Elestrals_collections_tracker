---
id: 005-collection-entry
unit: 004-collection-experience
intent: 001-collection-tracker
type: ddd-construction-bolt
status: partial
stories:
  - 016-fast-add-flow
  - 017-set-grid-entry
  - 018-undo-recent-adds
created: 2026-08-09T12:00:00Z
started: 2026-08-15T17:00:00Z
completed: null
current_stage: done
stages_completed:
  - name: model
    completed: 2026-08-15T17:00:00Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-08-15T17:20:00Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-15T17:35:00Z
    artifact: adr-005-delta-adjust-compare-and-swap.md
  - name: implement
    completed: 2026-08-16T00:50:00Z
    artifact: backend /adjust + frontend session, entry surfaces
  - name: test
    completed: 2026-08-17T18:45:00Z
    artifact: ddd-03-test-report.md

requires_bolts:
  - 003-card-catalog-surface
  - 004-inventory-core
enables_bolts:
  - 006-collection-browse
requires_units: []
blocks: false

complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: 005-collection-entry

## Overview

The two entry flows: keyboard-first single add, and whole-set grid entry. Plus undo, because speed
without recovery is just risk.

## Objective

Hit the numbers that decide whether this product survives contact with a real collection: **median
single-add under 5 seconds, 100 cards under 10 minutes**, keyboard only.

## Stories Included

- **016-fast-add-flow**: type → arrow → `Enter`, with carry-forward (Must)
- **017-set-grid-entry**: click +1, shift-click −1 over a whole set (Must)
- **018-undo-recent-adds**: undo the last 20 adds (Should)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. model**: Done → ddd-01-domain-model.md
- [x] **2. design**: Done → ddd-02-technical-design.md
- [x] **3. implement**: Done → `frontend/src/pages/collection/add/`
- [x] **4. test**: Done → ddd-03-test-report.md — automated in full; **the timed session with a real
      person has not been run**, and it is the one criterion that decides this bolt

## Dependencies

### Requires
- 003-card-catalog-surface (the search contract)
- 004-inventory-core (the write model, and its concurrency guarantee)

### Enables
- 006-collection-browse (there is finally data worth browsing)

## Success Criteria

- [x] Focus is in the search field on load; no click needed to start
- [x] `type 3 chars → ↓ → Enter` adds, clears and refocuses
- [x] Condition and finish carry forward between adds
- [x] Session tally with the last five adds; undo works per-add
- [x] Grid mode: click +1, shift-click −1, no reload, badges update instantly
- [x] Optimistic add reverts **visibly** on failure, naming the card
- [x] Screen reader announces success and failure via a live region — *this one failed first; see
      the test report's "two bugs the test stage caught"*
- [ ] **Measured**: median add < 5s, 100 cards < 10min, with a first-time user
- [x] Coverage > 80%, including a component test pinning the keyboard contract — 95.4% on the
      bolt's surface, and `AddSearchBox.test.tsx` is that test

## Notes

Entry is bolted **before** browsing deliberately. Browsing an empty collection proves nothing; the
moment entry works there is real data, and the timing target can be measured rather than estimated.

If the 5-second median is missed, fix the *interaction* — fewer required fields, better defaults,
more aggressive carry-forward. Do not respond by optimising an API that is already answering in
200ms. The bottleneck will be decisions the user has to make, not milliseconds.

## Construction result - 2026-08-17

**Status: partial.** All three stories are built and tested; the bolt stays `partial` on one
criterion rather than one story.

| Story | State |
|---|---|
| 016 fast-add flow | done — the keyboard contract is pinned test-by-test in `AddSearchBox.test.tsx` |
| 017 set grid entry | done — click +1, shift-click −1, bursts coalesce into one add *and one undo entry* |
| 018 undo recent adds | done — `POST /inventory/{id}/adjust` (ADR-005), 20-deep session stack, refusal carries both numbers |

**What is not done: the timed session with a real person.** Median add under five seconds and 100
cards under ten minutes is the bolt's objective and no test suite can measure it. Everything the
automated tests prove is that the interaction is *correct*; whether it is *fast enough for a
first-time collector* is unanswered. That is why this reads `partial` and not `complete`.

**The bug worth recording.** The live region was silent on the second of two identical adds — the
exact case of emptying a box of duplicates. Stage 3 carried a timestamp in the announcement so two
identical messages would "still re-announce"; the first reducer test failed because both adds landed
inside one millisecond. Fixing that exposed the real half: the timestamp was never rendered, so the
DOM never changed, so there was nothing for a screen reader to announce however distinct the state
was. `LiveAnnouncer` now double-buffers each politeness level. A criterion this bolt lists would
otherwise have shipped broken and been found by a screen-reader user.

A second, smaller one: the atomic `UPDATE` in `compare_and_adjust` bypasses the ORM, so the identity
map kept serving the pre-update quantity — the same lesson `upsert_merge` records from bolt 004,
learned again one method over.

`scripts/verify_mysql.py` gained steps [8] and [9] for the compare-and-swap under MySQL's own row
locking. Written, unrun — they need the platform stack, like the harvester's grant tests.
