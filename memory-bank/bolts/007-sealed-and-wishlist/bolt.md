---
id: 007-sealed-and-wishlist
unit: 005-sealed-and-wishlist
intent: 001-collection-tracker
type: simple-construction-bolt
status: planned
stories:
  - 025-sealed-inventory
  - 026-wishlist
created: 2026-08-09T12:00:00Z
started: null
completed: null
current_stage: null
stages_completed: []

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

- [ ] **1. implement**: Pending → migrations, services, `/sealed`, `/wishlist`
- [ ] **2. test**: Pending → test report

## Dependencies

### Requires
- 004-inventory-core (the ownership and merge patterns it reuses)

### Enables
- 008-import-export (export covers all three inventories)

## Success Criteria

- [ ] Sealed items never appear in `/collection` and never affect completion
- [ ] "Mark as opened" flips a flag and creates **no** singles
- [ ] A printing cannot be wished twice
- [ ] Acquiring a wished printing prompts, and only clears the wish on confirmation
- [ ] Same ownership guarantees and cross-user tests as bolt 004
- [ ] Coverage > 80%

## Notes

This is the smallest bolt in the intent and the right place to absorb schedule pressure if 005 or
006 overrun — the wishlist is `Should`, and the product is usable without it.

Resist the temptation to auto-generate singles when a box is marked opened. The expected
distribution is never the actual pull, so it would be wrong every single time, and it would be
wrong in a way the user has to hunt down and correct.
