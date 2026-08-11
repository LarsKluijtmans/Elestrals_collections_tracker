---
unit: 003-inventory-core
bolt: 004-inventory-core
stage: design
status: complete
updated: 2026-08-11T10:20:00Z
---

# Technical Design - Inventory Core

## Architecture Pattern

Unchanged: `Controllers → Services → Repositories → SQLAlchemy → MySQL`.

One rule is applied more strictly here than anywhere else, because the failure is silent:
**the service holds no `Session`.** The atomic upsert and the transaction boundary both live in
`InventoryRepository`, so "repositories are the only code that touches the database" stays
literally true rather than eroding one convenient call at a time.

## The merge discriminator

The data model's proposed key —
`UNIQUE (user_sub, printing_id, condition, is_graded, grader, grade)` — cannot express the rule
it is meant to enforce. Under it, two PSA 9 copies of the same printing collide and merge into
`quantity 2`, destroying the fact that they are two separately serialised, separately valuable
objects.

**Decision: a `merge_condition` column, `UNIQUE (user_sub, printing_id, merge_condition).`**

| Row kind | `merge_condition` | Behaviour |
|---|---|---|
| Ungraded | the condition (`near_mint`, …) | Collides with an identical row → merges |
| Graded | **NULL** | NULLs are distinct in a UNIQUE index on both MySQL and SQLite → never collides |

The whole policy is one nullable column. No service branch can be forgotten, and no concurrent
request can slip between a check and a write.

## Idempotent, concurrency-safe add

```sql
-- MySQL
INSERT INTO inventory_items (...) VALUES (...)
ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity), updated_at = ...

-- SQLite (tests)
INSERT INTO inventory_items (...) VALUES (...)
ON CONFLICT (user_sub, printing_id, merge_condition)
DO UPDATE SET quantity = quantity + excluded.quantity, updated_at = ...
```

`InventoryRepository.upsert_merge` branches on `session.get_bind().dialect.name`. One statement
in both cases; the database resolves the race.

**One consequence had to be handled explicitly:** the upsert is a Core statement, so the ORM
identity map still holds whatever quantity it last loaded. Reading the merged row back through
the same session returns the *pre-increment* value — correct in the database, wrong everywhere
the caller can see it. `upsert_merge` therefore calls `expire_all()` after flushing. This was a
real bug, caught by a test, not by review.

## Completion recompute

In the **same transaction** as the write:

```
add/edit/remove → flush
                → CompletionService.recompute(user_sub, sets touched)
                → repository.commit()
```

`recompute` measures from inventory (`COUNT(DISTINCT card_id)` and `SUM(quantity)` joined
through printings) and upserts `set_completion`. It flushes and never commits. A failure
propagates and the inventory write rolls back with it — a summary table that can drift from its
source is worse than no summary table.

`rebuild_for_user` regenerates the whole projection from inventory. That is the repair path for
a bad migration, a bug, or a restore.

## API Design

| Endpoint | Method | Auth | Notes |
|---|---|---|---|
| `/api/v1/inventory` | `POST` | user | `201` + `{item, merged}` |
| `/api/v1/inventory` | `GET` | user | Owner-scoped listing, cursor-paged. The filtered virtualised table is story 019 in bolt 006 |
| `/api/v1/inventory/{id}` | `PATCH` | user | A condition change may merge into an existing row |
| `/api/v1/inventory/{id}` | `DELETE` | user | `204` |
| `/api/v1/completion` | `GET` | user | Per-set completion + totals |

`merged` is on the wire because a collector who sees no new row wonders where their card went.

**`/completion` is a separate endpoint, not a field on `/sets`.** `/sets` is public and cached
for five minutes; completion is per-user. Merging them would put one collector's data behind a
shared cache key.

## Security Design

| Concern | Approach |
|---|---|
| Identity | The validated JWT `sub`, never a client-supplied id |
| Ownership | Repository methods take `user_sub` first and required; there is no unscoped getter |
| Cross-user access | **404, never 403.** Distinguishing "gone" from "not yours" is an enumeration oracle over the whole table. One explicit test per endpoint |
| Referential integrity | `printing_id` is `ON DELETE RESTRICT` — a catalog cleanup must never silently delete someone's collection |
| Bounds | `quantity` 1–10,000 in Pydantic *and* a `CHECK (quantity > 0)` in the schema |

## NFR Implementation

| Requirement | Approach |
|---|---|
| Write p95 < 200ms incl. recompute | One upsert + two aggregates scoped to the touched sets, all on `(user_sub, …)` indexes. Unmeasured — needs MySQL |
| Recompute < 50ms p95 | Recompute is scoped to the sets a write touched, never the whole collection |
| Completion never disagrees | Same-transaction recompute; there is no window in which they can differ |
| Concurrent double-add → one row | Atomic upsert against the unique index |

## Error Handling

| Error | Code | Response |
|---|---|---|
| Unknown printing | `printing_not_found` | `404` |
| Unknown or other user's item | `inventory_item_not_found` | `404` |
| Quantity out of range | `quantity_out_of_range` | `400` (Pydantic returns `422` at the boundary) |
| Malformed cursor | `bad_request` | `400` |

Both codes are already in `api-conventions.md`; this bolt adds none.

## Stage 3 (ADR analysis) — recommendation

**Skip.** The one decision with architectural weight — the `merge_condition` discriminator — is
a deviation from `standards/data-model.md` and is recorded there and in the test report. It
constrains this table only, not the system.
