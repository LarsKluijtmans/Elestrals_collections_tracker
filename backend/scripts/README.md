# Integration checks against a real database

The unit suite runs on in-memory SQLite. These two scripts run against whatever
`DATABASE_URL` points at — in practice the platform's MySQL — and cover the things SQLite
cannot answer.

Run them from `backend/` with the venv active:

```bash
PYTHONPATH=. python scripts/verify_mysql.py   # correctness on the real engine
PYTHONPATH=. python scripts/bench.py          # the NFR budgets
```

Both seed their own data under a reserved set code and delete it again, so they are safe to
re-run against a database that has real content.

## `verify_mysql.py` — 24 checks

Importer against MySQL · idempotent re-run (0 added / 0 updated) · coverage against the declared
printed size · search ranking and stable order · inventory merge · **graded copies staying
separate, which depends on MySQL treating NULLs as distinct in a unique index** · four
concurrent adds collapsing to one row · completion recomputed in the same transaction ·
`app_logs` written by the real logging path.

## `bench.py` — the five NFR budgets

Seeds ~5,000 cards / 7,500 printings, the size `unit-brief.md` projects, then measures full
import, idempotent re-import, search p95, inventory write p95 including recompute, and recompute
alone.

Measured 2026-08-11 on MySQL 8.4:

| | budget | measured |
|---|---|---|
| Full import (5,000 cards) | 15 min | 34.4s |
| Search p95 (3-char prefix) | 150ms | **26.9ms** |
| Inventory write p95 incl. recompute | 200ms | **16.1ms** |
| Recompute alone p95 | 50ms | **5.4ms** |
