---
id: 007-sealed-and-wishlist
unit: 005-sealed-and-wishlist
intent: 001-collection-tracker
type: simple-construction-bolt
status: complete
stories:
  - 025-sealed-inventory
  - 026-wishlist
created: 2026-08-09T12:00:00Z
started: 2026-08-17T20:20:00Z
completed: 2026-08-17T20:40:00Z
current_stage: done
stages_completed:
  - name: implement
    completed: 2026-08-17T20:35:00Z
    artifact: 0005_sealed_and_wishlist.py, 2 services, /sealed, /wishlist
  - name: test
    completed: 2026-08-17T20:40:00Z
    artifact: test-report.md

requires_bolts:
  - 004-inventory-core
enables_bolts:
  - 008-import-export
requires_units: []
blocks: false

complexity:
  avg_complexity: 1
  avg_uncertainty: 1
  max_dependencies: 1
  testing_scope: 2
---

# Bolt: 007-sealed-and-wishlist

## Overview

Sealed product inventory and the wishlist — two thin surfaces over patterns bolt 004 already
established.

## Objective

Track packs, boxes and decks without them ever contaminating singles maths, and keep a want-list
that phase 2 can attach alerts to.

## Stories Included

- **025-sealed-inventory**: sealed holdings with an opened flag (Must)
- **026-wishlist**: wanted printings with a max price (Should)

## Bolt Type

**Type**: Simple Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/simple-construction-bolt.md`

A *simple* bolt rather than DDD on purpose: the domain modelling for owned-quantity-of-a-thing was
done in bolt 004. Re-running a full DDD cycle here would produce ceremony, not insight.

## Stages

- [x] **1. implement**: Done → `0005_sealed_and_wishlist.py`, two services, `/sealed`, `/wishlist`
- [x] **2. test**: Done → `test-report.md` — 41 tests, one per endpoint for cross-user access

## Dependencies

### Requires
- 004-inventory-core (the ownership and merge patterns it reuses)

### Enables
- 008-import-export (export covers all three inventories)

## Success Criteria

- [x] Sealed items never appear in `/collection` and never affect completion — true **by
      construction**: they are not in the table those queries read
- [x] "Mark as opened" flips a flag and creates **no** singles
- [x] A printing cannot be wished twice — unique index, plus a `409` with a sentence
- [x] Acquiring a wished printing prompts, and only clears the wish on confirmation
- [x] Same ownership guarantees and cross-user tests as bolt 004 — one per endpoint
- [x] Coverage > 80%

## Notes

This is the smallest bolt in the intent and the right place to absorb schedule pressure if 005 or
006 overrun — the wishlist is `Should`, and the product is usable without it.

Resist the temptation to auto-generate singles when a box is marked opened. The expected
distribution is never the actual pull, so it would be wrong every single time, and it would be
wrong in a way the user has to hunt down and correct.

## Construction result - 2026-08-17

**Status: complete.** Both stories built, every criterion met — the first bolt in this intent to
close without an asterisk.

| Story | State |
|---|---|
| 025 sealed inventory | done — own table, merge on `(product, is_sealed)`, opening creates no singles |
| 026 wishlist | done — one wish per printing, money is never half-set, acquiring prompts rather than clears |

**Sealed lives in its own table**, and that is what makes story 025's third criterion structural
rather than a rule someone has to remember. A `kind` column on `inventory_items` would have put the
burden on every future query to exclude sealed, and the query that forgets counts a booster box as a
card. `is_sealed` being part of the unique key is the same trick `merge_condition` plays in bolt
004, one case simpler because there is no NULL here.

**The bug worth recording.** `WishlistService.edit` validated with
`fields.desired_quantity or item.desired_quantity`, and `0 or x` is `x` — so a patch setting the
quantity to zero fell through to the stored value, validated that instead, and handed the zero to
the database. The CHECK constraint caught it as an `IntegrityError`, which is the right failure in
the wrong place: a 400 with a sentence, not a constraint name. Fixed with `is not None`.

Worth noticing that the constraint is what turned a silent bad write into a loud bad error. It was
added for correctness and paid off as a diagnostic.

