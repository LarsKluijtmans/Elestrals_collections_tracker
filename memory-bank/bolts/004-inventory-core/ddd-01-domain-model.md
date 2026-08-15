---
unit: 003-inventory-core
bolt: 004-inventory-core
stage: model
status: complete
updated: 2026-08-11T10:00:00Z
---

# Static Model - Inventory Core

Covers `013-add-inventory-item`, `014-edit-inventory-item`, `015-remove-inventory-item`,
`023-set-completion`.

## Bounded Context

**Ownership.** The catalog says what exists; this context says who has it. It points *at*
`printings` and never modifies them, and nothing in the catalog context may read inventory —
that separation is what keeps `/cards` and `/sets` cacheable and user-agnostic.

The identity here is always the JWT `sub`. There is no user table to join, no client-supplied
owner id, and no endpoint that takes one.

## Domain Entities

| Entity | Properties | Business Rules |
|---|---|---|
| **InventoryItem** | `user_sub`, `printing_id`, `condition`, `quantity`, `is_graded`, `grader`, `grade`, `merge_condition`, acquisition fields, `storage_location`, `notes`, `is_for_trade` | `quantity > 0` — a zero-quantity row is a deletion that did not happen. Ungraded rows for one `(user, printing, condition)` **merge**; graded copies never do. Points at a Printing, never a Card |
| **SetCompletion** | `user_sub`, `set_id`, `owned_cards`, `card_count`, `total_quantity` | A projection, never a source. Recomputed inside the transaction that changed inventory; if the recompute fails the write rolls back with it |

## Value Objects

| Value Object | Properties | Constraints |
|---|---|---|
| **MergeKey** | `condition` when ungraded, **NULL** when graded | The whole merge policy in one nullable column. NULLs are distinct in a UNIQUE index on both MySQL and SQLite, so graded copies get their own rows structurally rather than by a service branch someone can forget |
| **Condition** | `mint`…`damaged` | Closed set. An unknown condition is rejected, never coerced |
| **Grading** | `is_graded`, `grader`, `grade` | A graded copy is an individually meaningful object — its own serial, its own value, sellable separately |
| **Money** | `acquired_unit_price_cents`, `acquired_currency` | Integer cents and an explicit currency. Never a float, never a bare number |
| **CompletionView** | `owned_cards`, `card_count`, `total_quantity`, `ratio` | `ratio` is guarded: a set with no declared printed size has no percentage, and `x/0` is not renderable |

## Aggregates

| Aggregate Root | Members | Invariants |
|---|---|---|
| **InventoryItem** | — | Each row is its own aggregate. There is no "Collection" root: it would span every row a user owns, could never be loaded to enforce anything, and would serialise every concurrent add — the exact opposite of what the fast-add flow needs |
| **SetCompletion** | — | Derived. Its only invariant is agreement with inventory, and that is enforced by transaction scope rather than by the aggregate |

### The invariant this bolt exists for

> **Adding the same ungraded printing twice yields one row with quantity 2 — even when both
> requests arrive at the same instant.**

The fast-add flow fires concurrent requests by design; a collector emptying a box types faster
than a round trip. A read-then-write passes every sequential test and loses rows in production,
so the merge is a **single atomic upsert** against `(user_sub, printing_id, merge_condition)`.
The database resolves the race. No code path checks-then-writes.

## Domain Events

| Event | Trigger | Payload |
|---|---|---|
| **ItemAdded** | a new row is created | `user_sub`, `item_id`, `printing_id`, `quantity` |
| **ItemMerged** | an add folds into an existing row | `user_sub`, `item_id`, `added_quantity`, `new_total` |
| **ItemEdited** | fields change, possibly merging two rows | `user_sub`, `item_id`, changed fields, `merged_into` |
| **ItemRemoved** | a row is deleted | `user_sub`, `item_id`, `printing_id` |
| **CompletionRecomputed** | any of the above commits | `user_sub`, `set_id`, `owned_cards`, `card_count` |

`ItemMerged` is distinct from `ItemAdded` because the UI needs it: a collector who sees no new
row wonders where their card went. "Now 3" is the correct feedback.

## Domain Services

| Service | Operations | Dependencies |
|---|---|---|
| **InventoryService** | `add`, `edit`, `remove`, `list_items`, `count`, `total_quantity` | InventoryRepository, PrintingRepository, CompletionService. Owns the transaction boundary: a write and its recompute commit together or not at all |
| **CompletionService** | `recompute(user, set_ids)`, `rebuild_for_user(user)`, `view(user)` | SetCompletionRepository, SetRepository. Flushes, never commits — the caller's transaction is the point |

## Repository Interfaces

| Repository | Entity | Methods |
|---|---|---|
| **InventoryRepository** | InventoryItem | `get(user_sub, id)`, `find_mergeable(user_sub, printing_id, merge_condition)`, `find_twin(...)`, `list_for_user(user_sub, …)`, `count_for_user`, `total_quantity`, `upsert_merge(values)`, `remove(user_sub, id)`, `set_ids_touched_by`, `flush`, `commit`, `rollback` |
| **SetCompletionRepository** | SetCompletion | `get(user_sub, set_id)`, `measure(user_sub, set_id)`, `upsert(user_sub, set_id, …)`, `list_for_user(user_sub)`, `all_set_ids` |

**Every method takes `user_sub` first and required.** There is deliberately no `get(item_id)`
on the inventory repository at all: an unscoped query should be impossible to write, not merely
discouraged in review.

## Ubiquitous Language

| Term | Definition |
|---|---|
| **Item** | One row: N copies of a printing in a condition, owned by one person |
| **Merge** | Folding an add into an existing row by raising its quantity. Ungraded only |
| **Graded copy** | An individually meaningful object with a grader and grade. Never merges, not even with an identical grade |
| **Coverage** | How much of a set the *catalog* holds (bolt 002) |
| **Completion** | How much of a set a *person* owns. A different word from coverage on purpose — conflating them is how "you own 100%" appears for a set we half-imported |
| **Owned cards** | Distinct cards with at least one printing owned. The completion numerator; cards, not printings, because the wrong denominator reads above 100% |

## Story coverage

| Story | Covered by |
|---|---|
| `013-add-inventory-item` | InventoryItem, MergeKey, atomic upsert, `ItemAdded`/`ItemMerged` |
| `014-edit-inventory-item` | `edit`, `find_twin`, condition-change merge |
| `015-remove-inventory-item` | `remove`, `ItemRemoved` |
| `023-set-completion` | SetCompletion, CompletionService, transaction-scoped recompute, rebuild |
