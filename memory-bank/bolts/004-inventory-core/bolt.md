---
id: 004-inventory-core
unit: 003-inventory-core
intent: 001-collection-tracker
type: ddd-construction-bolt
status: planned
stories:
  - 013-add-inventory-item
  - 014-edit-inventory-item
  - 015-remove-inventory-item
  - 023-set-completion
created: 2026-08-09T12:00:00Z
started: null
completed: null
current_stage: null
stages_completed: []

requires_bolts:
  - 002-card-catalog-schema-import
enables_bolts:
  - 005-collection-entry
  - 006-collection-browse
  - 007-sealed-and-wishlist
  - 008-import-export
  - 009-profile-and-sharing
requires_units: []
blocks: false

complexity:
  avg_complexity: 3
  avg_uncertainty: 1
  max_dependencies: 1
  testing_scope: 2
---

# Bolt: 004-inventory-core

## Overview

The domain heart: the inventory write model, its invariants, unforgeable ownership, and the set
completion projection.

## Objective

A user can own *N* copies of a printing in a condition, and every rule that keeps that coherent is
enforced in the database and the service layer — not in the UI.

## Stories Included

- **013-add-inventory-item**: add with merge-on-duplicate (Must)
- **014-edit-inventory-item**: edit, including merging conditions (Must)
- **015-remove-inventory-item**: explicit, confirmed removal (Must)
- **023-set-completion**: the projection, recomputed on write (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [ ] **1. model**: Pending → ddd-01-domain-model.md
- [ ] **2. design**: Pending → ddd-02-technical-design.md
- [ ] **3. implement**: Pending → `backend/app/{models,repositories,services,controllers}/inventory*`
- [ ] **4. test**: Pending → ddd-03-test-report.md

## Dependencies

### Requires
- 002-card-catalog-schema-import (`printings` must exist to point at)

### Enables
- Every remaining bolt in the intent

## Success Criteria

- [ ] Same printing+condition added twice → one row, quantity 2
- [ ] Same printing graded PSA 9 and PSA 10 → two rows
- [ ] **Concurrent** double-add → quantity 2, not two rows (tested under real concurrency)
- [ ] Another user's item id → 404, never 403
- [ ] Completion correct immediately after a write, no refresh, and never disagreeing with inventory
- [ ] Completion rebuild command regenerates the whole projection from inventory
- [ ] Write p95 < 200ms including recompute; recompute itself < 50ms p95
- [ ] An explicit cross-user access test exists for **every** endpoint
- [ ] Coverage > 80%

## Notes

Two rules that must be enforced structurally, not by convention:

1. **Merge-on-duplicate via upsert**, not read-then-write. The fast-add flow fires concurrent
   requests by design; a read-then-write passes every sequential test and loses rows in production.
2. **Repository methods take `user_sub` first and required.** An unscoped query should be
   impossible to write, not merely discouraged in review.

Completion recompute lives in the same transaction as the write. If recompute fails, the write rolls
back. A summary table that can drift from its source is worse than no summary table.
