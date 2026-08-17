---
id: 004-inventory-core
unit: 003-inventory-core
intent: 001-collection-tracker
type: ddd-construction-bolt
status: complete
stories:
  - 013-add-inventory-item
  - 014-edit-inventory-item
  - 015-remove-inventory-item
  - 023-set-completion
created: 2026-08-09T12:00:00Z
started: 2026-08-10T18:00:00Z
completed: 2026-08-11T23:00:00Z
current_stage: done
stages_completed:
  - name: model
    completed: 2026-08-10T19:00:00Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-08-10T21:00:00Z
    artifact: ddd-02-technical-design.md
  - name: implement
    completed: 2026-08-11T09:00:00Z
    artifact: 2 models, 0003_inventory.py, 2 repositories, 2 services, 5 endpoints
  - name: test
    completed: 2026-08-11T23:00:00Z
    artifact: ddd-03-test-report.md

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

- ✅ **1. model**: Complete → `ddd-01-domain-model.md`
- ✅ **2. design**: Complete → `ddd-02-technical-design.md`
- ⏭️ **3. ADR analysis** *(optional)*: skipped — the one weighty decision (the merge
  discriminator) constrains one table, and is recorded in the design and test report.
- ✅ **4. implement**: Complete → 2 models, `0003_inventory.py`, 2 repositories, 2 services,
  5 endpoints
- ✅ **5. test**: Complete → `ddd-03-test-report.md`

  157 tests pass (38 new) · 92% on bolt-004 modules · concurrent double-add proven with two
  real threads on two connections. The report was written `partial` on the strength of one
  unmeasured criterion; the verification run on **2026-08-11** closed it — `scripts/bench.py`
  measured **write p95 16.1ms** against a 200ms budget and **recompute p95 5.4ms** against 50ms,
  and `scripts/verify_mysql.py` proved four concurrent adds collapse to one row on MySQL itself.

## Dependencies

### Requires
- 002-card-catalog-schema-import (`printings` must exist to point at)

### Enables
- Every remaining bolt in the intent

## Success Criteria

- [x] Same printing+condition added twice → one row, quantity 2
- [x] Same printing graded PSA 9 and PSA 10 → two rows — and two PSA 9s also stay two rows
- [x] **Concurrent** double-add → quantity 2, not two rows (tested under real concurrency) — two
      threads on SQLite, and four on MySQL in `verify_mysql.py`
- [x] Another user's item id → 404, never 403
- [x] Completion correct immediately after a write, no refresh, and never disagreeing with inventory
- [x] Completion rebuild command regenerates the whole projection from inventory
- [x] Write p95 < 200ms including recompute; recompute itself < 50ms p95 — **16.1ms / 5.4ms**
- [x] An explicit cross-user access test exists for **every** endpoint
- [x] Coverage > 80% — 92%

## Notes

Two rules that must be enforced structurally, not by convention:

1. **Merge-on-duplicate via upsert**, not read-then-write. The fast-add flow fires concurrent
   requests by design; a read-then-write passes every sequential test and loses rows in production.
2. **Repository methods take `user_sub` first and required.** An unscoped query should be
   impossible to write, not merely discouraged in review.

Completion recompute lives in the same transaction as the write. If recompute fails, the write rolls
back. A summary table that can drift from its source is worse than no summary table.
