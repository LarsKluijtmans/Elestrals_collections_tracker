---
unit: 005-sealed-and-wishlist
intent: 001-collection-tracker
phase: inception
status: complete
created: '2026-08-09T12:00:00Z'
updated: '2026-08-09T12:00:00Z'
---

# Unit Brief: sealed-and-wishlist

## Purpose

The two inventories adjacent to singles: **sealed product** (packs, boxes, decks, bundles), which is
tracked and valued separately and must never contaminate singles maths; and the **wishlist**, the
inverse of inventory and the seed for phase-2 price alerts and phase-3 want-matching.

## Scope

### In Scope
- `sealed_inventory_items` and `wishlist_items`
- `/sealed` and `/wishlist` pages
- The explicit "mark as opened" action on a sealed product
- "Acquired this" prompt to clear a wishlist entry when the printing enters inventory

### Out of Scope
- The sealed product *catalog* (unit 002 owns `sealed_products`)
- Price alerts on wishlist entries (intent 002)
- Want-matching against listings (intent 003)

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-11 | Sealed product inventory | Must |
| FR-12 | Wishlist | Should |

---

## Domain Concepts

### Key Entities
| Entity | Description | Attributes |
|--------|-------------|------------|
| SealedInventoryItem | A held sealed product | `user_sub`, `sealed_product_id`, `quantity`, `is_sealed`, cost basis, location |
| WishlistItem | A wanted printing | `user_sub`, `printing_id`, `desired_quantity`, `max_price_cents`, `priority` |

### Key Operations
| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `add_sealed` | Add or merge a sealed holding | `sub`, product, qty, sealed? | item |
| `mark_opened` | Flip `is_sealed` to false | `sub`, item id | item |
| `add_wish` | Add a wanted printing | `sub`, printing, qty, max price | item |
| `resolve_wish` | Clear a wish when acquired | `sub`, printing | none |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 2 |
| Must Have | 1 |
| Should Have | 1 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 025-sealed-inventory | Track sealed product | Must | Planned |
| 026-wishlist | Keep a wishlist | Should | Planned |

---

## Dependencies

### Depends On
| Unit | Reason |
|------|--------|
| 002-card-catalog | `sealed_products` and `printings` |
| 003-inventory-core | Reuses its ownership and merge patterns |

### Depended By
| Unit | Reason |
|------|--------|
| 006-import-export | Export covers singles, sealed and wishlist together |

### External Dependencies
None.

---

## Technical Context

### Suggested Technology
Same repository and service patterns as unit 003, deliberately — these are structurally the same
problem with a different target table, and any divergence is accidental complexity.

### Integration Points
| Integration | Type | Protocol |
|-------------|------|----------|
| Our API | REST | `/api/v1/sealed`, `/api/v1/wishlist` |

### Data Storage
| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| `sealed_inventory_items` | SQL | small relative to singles | life of account |
| `wishlist_items` | SQL | small | life of account |

---

## Constraints

- **Sealed never enters singles maths.** Not in set completion, not in the singles table, not in a
  singles export. A sealed box contains cards, but the user does not own those cards until they say
  so.
- **Opening a box creates nothing automatically.** `mark_opened` flips a flag. Generating singles
  from a box would be inventing data the user did not enter, and it would be wrong every time the
  pull differs from the expected distribution — which is always.
- A printing appears at most once per user in the wishlist.
- Owning a printing does not silently remove the wish — it *offers* to, because a collector may want
  a second copy or a better condition.

---

## Success Criteria

### Functional
- [ ] Sealed items never appear in `/collection` or affect any completion percentage
- [ ] Marking a box opened changes only the flag
- [ ] A printing cannot be wished twice
- [ ] Acquiring a wished printing prompts, and only removes the wish on confirmation

### Non-Functional
- [ ] Both pages load p95 < 300ms
- [ ] Same ownership guarantees as unit 003, with the same cross-user tests

### Quality
- [ ] Code coverage > 80%
- [ ] Code reviewed and approved

---

## Bolt Suggestions

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| 007-sealed-and-wishlist | simple | 025, 026 | Two thin CRUD surfaces over established patterns — a simple bolt, not a DDD one, because the domain modelling was already done in unit 003 |

---

## Notes

This is the smallest unit in the intent and the right place to absorb schedule pressure if bolts
005 and 006 overrun. The wishlist is `Should`, not `Must`: a collector can use the product without
it. Sealed tracking is `Must` because the user named packs and boosters explicitly as phase-1 scope.
