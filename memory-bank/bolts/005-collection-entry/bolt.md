---
id: 005-collection-entry
unit: 004-collection-experience
intent: 001-collection-tracker
type: ddd-construction-bolt
status: planned
stories:
  - 016-fast-add-flow
  - 017-set-grid-entry
  - 018-undo-recent-adds
created: 2026-08-09T12:00:00Z
started: null
completed: null
current_stage: null
stages_completed: []

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

- [ ] **1. model**: Pending → ddd-01-domain-model.md
- [ ] **2. design**: Pending → ddd-02-technical-design.md
- [ ] **3. implement**: Pending → `frontend/src/pages/collection/add/`
- [ ] **4. test**: Pending → ddd-03-test-report.md, **including a timed session with a real person**

## Dependencies

### Requires
- 003-card-catalog-surface (the search contract)
- 004-inventory-core (the write model, and its concurrency guarantee)

### Enables
- 006-collection-browse (there is finally data worth browsing)

## Success Criteria

- [ ] Focus is in the search field on load; no click needed to start
- [ ] `type 3 chars → ↓ → Enter` adds, clears and refocuses
- [ ] Condition and finish carry forward between adds
- [ ] Session tally with the last five adds; undo works per-add
- [ ] Grid mode: click +1, shift-click −1, no reload, badges update instantly
- [ ] Optimistic add reverts **visibly** on failure, naming the card
- [ ] Screen reader announces success and failure via a live region
- [ ] **Measured**: median add < 5s, 100 cards < 10min, with a first-time user
- [ ] Coverage > 80%, including a component test pinning the keyboard contract

## Notes

Entry is bolted **before** browsing deliberately. Browsing an empty collection proves nothing; the
moment entry works there is real data, and the timing target can be measured rather than estimated.

If the 5-second median is missed, fix the *interaction* — fewer required fields, better defaults,
more aggressive carry-forward. Do not respond by optimising an API that is already answering in
200ms. The bottleneck will be decisions the user has to make, not milliseconds.
