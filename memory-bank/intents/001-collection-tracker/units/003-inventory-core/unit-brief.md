---
unit: 003-inventory-core
intent: 001-collection-tracker
phase: inception
status: complete
created: '2026-08-09T12:00:00Z'
updated: '2026-08-09T12:00:00Z'
---

# Unit Brief: inventory-core

## Purpose

The domain heart: a user owns *N* copies of a specific printing in a specific condition, optionally
with a cost basis. This unit owns the write model, the invariants that keep it coherent, and the set
completion projection derived from it.

## Scope

### In Scope
- `inventory_items` and the `set_completion` summary table
- Add / edit / remove, with the merge-on-duplicate invariant
- Ownership enforcement — every repository method is scoped to `user_sub`
- Cost basis, acquisition date, storage location, grading, notes, for-trade flag
- Completion recomputation on write
- The list/filter API the collection table consumes

### Out of Scope
- Any UI (unit 004)
- Sealed and wishlist (unit 005)
- Valuation (intent 002) — but `acquired_unit_price_cents` is captured here so phase 2 has history

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-7 | Record owned singles | Must |
| FR-10 | Set completion | Must |

---

## Domain Concepts

### Key Entities
| Entity | Description | Attributes |
|--------|-------------|------------|
| InventoryItem | A holding of one printing in one condition | `user_sub`, `printing_id`, `condition`, `quantity`, grading, cost basis, location, notes, `is_for_trade` |
| SetCompletion | Derived per user per set | `user_sub`, `set_id`, `owned_printings`, `total_printings`, `percentage` |
| CollectionSnapshot | Nightly point-in-time count | `user_sub`, `taken_on`, `item_count`, `distinct_printings` |

### Key Operations
| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `add_item` | Add or merge into an existing holding | `sub`, printing, condition, qty, meta | `InventoryItem` |
| `adjust_quantity` | Increment/decrement | `sub`, item id, delta | `InventoryItem` or removal |
| `update_item` | Edit metadata | `sub`, item id, patch | `InventoryItem` |
| `remove_item` | Explicit delete | `sub`, item id | none |
| `list_items` | Filtered, sorted, paged | `sub`, filters | page of items |
| `recompute_completion` | Refresh the projection for affected sets | `sub`, set ids | none |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 4 |
| Must Have | 4 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 013-add-inventory-item | Add a card to my collection | Must | Planned |
| 014-edit-inventory-item | Edit a holding | Must | Planned |
| 015-remove-inventory-item | Remove a holding | Must | Planned |
| 023-set-completion | Set completion percentage | Must | Planned |

---

## Dependencies

### Depends On
| Unit | Reason |
|------|--------|
| 001-platform-foundation | DB, auth, logging |
| 002-card-catalog | `printings` must exist to point at |

### Depended By
| Unit | Reason |
|------|--------|
| 004 | The table and entry flows are this unit's UI |
| 005 | Sealed and wishlist mirror these patterns |
| 006 | Import writes through these services; export reads them |

### External Dependencies
| System | Purpose | Risk |
|--------|---------|------|
| logs-api | usage metering on add | Low |

---

## Technical Context

### Suggested Technology
SQLAlchemy 2.x typed models. **Repository methods take `user_sub` as their first positional
argument** — not as an optional filter — so an unscoped query is a signature error rather than a
silent data leak. Completion is a summary table refreshed in the same transaction as the write, not
a view and not a cache: it must never disagree with the inventory it summarises.

### Integration Points
| Integration | Type | Protocol |
|-------------|------|----------|
| Frontend | API | REST `/api/v1/inventory`, `/api/v1/completion` |
| logs-api | usage | M2M `usage.track` |

### Data Storage
| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| `inventory_items` | SQL | up to 10M | life of account |
| `set_completion` | SQL | users × sets | derived, rebuildable |
| `collection_snapshots` | SQL | users × days | 3 years |

---

## Constraints

- **Merge-on-duplicate**: adding an existing `(printing, condition)` for an ungraded copy increments
  quantity. Graded copies are individually identified and always separate rows.
- `quantity` is always ≥ 1. Reaching zero is a removal, and removal is an explicit action with
  confirmation — never an accidental side effect of a stepper.
- Every query filters on the validated `sub`. An item id from the client is *checked against* the
  caller's ownership, never trusted as proof of it.
- Completion updates inside the write transaction; a failed recompute rolls back the write.
- Cost basis is optional, and its absence must not break any later valuation maths.

---

## Success Criteria

### Functional
- [ ] Adding the same printing+condition twice yields one row with quantity 2
- [ ] Adding the same printing graded PSA 9 and PSA 10 yields two rows
- [ ] A request naming another user's item id returns 404 (not 403 — we do not confirm existence)
- [ ] Completion for a set is correct immediately after a write, with no refresh
- [ ] Removing the last copy removes the row and updates completion

### Non-Functional
- [ ] Inventory write p95 < 200ms including completion recompute
- [ ] Filtered list of 10k rows p95 < 400ms
- [ ] A concurrent double-add of the same printing produces quantity 2, not two rows (tested under
      real concurrency, not just in sequence)

### Quality
- [ ] Code coverage > 80%
- [ ] An explicit test asserting cross-user access is impossible for every endpoint
- [ ] Code reviewed and approved

---

## Bolt Suggestions

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| 004-inventory-core | DDD | 013, 014, 015, 023 | Write model, invariants, ownership, completion projection |

---

## Notes

The concurrency case is real, not theoretical: the fast-add flow fires optimistic requests in quick
succession, and a user holding the `+` key will race themselves. Merge-on-duplicate must be enforced
by the unique constraint with an upsert, not by a read-then-write in the service — the latter passes
every sequential test and fails in production.
