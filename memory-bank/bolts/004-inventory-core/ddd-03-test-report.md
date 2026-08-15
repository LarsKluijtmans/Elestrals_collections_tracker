---
unit: 003-inventory-core
bolt: 004-inventory-core
stage: test
status: partial
updated: 2026-08-11T11:00:00Z
---

# Test Report - Inventory Core

## Automated

```
backend/.venv → pytest        157 passed in 2.22s   (38 new in this bolt)
```

| Suite | Count | Covers |
|---|---|---|
| `test_inventory.py` | 15 | merge, graded separation, **real-thread concurrency**, ownership, edit-merge, validation |
| `test_inventory_api.py` | 13 | the five endpoints, plus one cross-user test each |
| `test_set_completion.py` | 10 | immediate correctness, cards-not-printings, rebuild, per-user isolation, ratio guard |

**Coverage: 92%** across bolt-004 modules. Whole app 86%.

## Success criteria

| Criterion | State |
|---|---|
| Same printing+condition twice → one row, quantity 2 | ✅ |
| PSA 9 and PSA 10 → two rows | ✅ — and two PSA 9s also stay two rows |
| **Concurrent** double-add → quantity 2, not two rows | ✅ on SQLite, two real threads on two connections |
| Another user's item id → 404, never 403 | ✅ one explicit test per endpoint |
| Completion correct immediately after a write | ✅ |
| Completion rebuild regenerates the projection | ✅ including sets the user owns nothing from |
| Write p95 < 200ms; recompute < 50ms | ❌ **unmeasured** — needs MySQL |
| Cross-user test for every endpoint | ✅ |
| Coverage > 80% | ✅ 92% |

## Two bugs the tests caught

**1. A stale read after the atomic upsert.** The merge is a Core `INSERT … ON CONFLICT`, so the
ORM identity map still held the pre-increment quantity. The database was correct and every
caller reading through the same session saw the old number — the second add returned
`quantity 1`. Fixed with `expire_all()` after the flush. The concurrency test had passed
throughout, because each thread held its own session; only the sequential test could see it.

**2. Dead code left behind by a refactor.** Moving the upsert into the repository left
`_atomic_upsert` in the service, still referencing imports that had been removed. Unreachable,
so no test failed. `ruff`'s `F821` found it.

## Deviation from `standards/data-model.md`

The data model proposes
`UNIQUE (user_sub, printing_id, condition, is_graded, grader, grade)` and notes that graded
copies are "exempt from the merge (enforced in the service, not the constraint)". **That key
cannot express the rule.** Under it, two PSA 9 copies of the same printing collide and merge
into `quantity 2`, destroying the fact that they are two separately serialised objects — and no
service-layer exemption can prevent it, because the constraint fires first.

Replaced with `merge_condition` (the condition when ungraded, NULL when graded) and
`UNIQUE (user_sub, printing_id, merge_condition)`. NULLs are distinct in a unique index on both
engines, so graded copies never collide. The policy is one column, enforced structurally, with
no service branch to forget. `standards/data-model.md` should be updated to match.

## What the concurrency test does and does not prove

Two real threads on two real connections, synchronised on a barrier, both adding the same
printing. It **proves the add path is a single atomic statement** — a read-then-write
implementation fails it, which is exactly the regression worth catching, since that
implementation passes every other test in the file.

It runs on file-backed SQLite. **MySQL's own `ON DUPLICATE KEY UPDATE` semantics, its locking
behaviour under contention, and the p95 targets remain unverified** until a server exists.


## Verified against real MySQL — 2026-08-11

The platform stack was already running (`../auth/docker-compose.yml`, 19 containers). Migrations
`0001`–`0003` applied to MySQL 8.4 cleanly, and `backend/scripts/verify_mysql.py` passed **24/24**
checks against it, `backend/scripts/bench.py` **5/5** NFR budgets. Both are re-runnable and clean
up after themselves.

What that closes for this bolt is listed below; anything still open stays listed as open.

| Was open | Now |
|---|---|
| Write p95 < 200ms incl. recompute | ✅ **16.1ms** |
| Recompute < 50ms p95 | ✅ **5.4ms** |
| MySQL `ON DUPLICATE KEY UPDATE` under contention | ✅ **four** concurrent adds → one row, quantity exactly 4 |
| Graded copies separate on MySQL | ✅ two identical PSA 9 copies stayed two rows — MySQL treats the NULL `merge_condition` as distinct, as the design depends on |
| Migration applied rather than generated | ✅ applied; `merge_condition` confirmed `nullable=YES` in `information_schema` |

The `merge_condition` design rested entirely on NULL-distinctness in a MySQL unique index. That
is now checked rather than assumed.

## Previously not verified — needs a running database

- Write and recompute latency (both targets)
- MySQL `ON DUPLICATE KEY UPDATE` under real contention
- `ON DELETE RESTRICT` on `printing_id` against a real catalog delete
- The migration applied rather than generated as SQL

## Not built here, deliberately

`GET /inventory` is an owner-scoped listing with cursor paging — enough to read back a write
and drive edit and remove. The filtered, sorted, virtualised collection table with its eight
filters is story 019 in bolt 006, and half-building it here would mean rewriting it there.
