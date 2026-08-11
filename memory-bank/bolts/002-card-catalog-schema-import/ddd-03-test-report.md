---
unit: 002-card-catalog
bolt: 002-card-catalog-schema-import
stage: test
status: partial
updated: 2026-08-10T14:20:00Z
---

# Test Report - Card Catalog

## Automated

```
backend/.venv → pytest
73 passed in 0.73s        (63 new in this bolt, 10 inherited from bolt 001)
```

| Suite | Count | Covers |
|---|---|---|
| `test_normaliser.py` | 21 | grouping, vocabulary aliases, every rejection reason, purity, totality |
| `test_catalog_upsert.py` | 7 | add / update / unchanged, per-entity fingerprints, **zero-write re-run** |
| `test_import_runner.py` | 8 | end-to-end fetch→normalise→upsert→report, run status, coverage warning |
| `test_admin_catalog_api.py` | 7 | 403 / 404 / 202, run detail shape, malformed cursor |
| `test_csv_seed_adapter.py` | 9 | comments, defaults, `source_ref`, honest failures |
| `test_coverage.py` | 6 | shortfall reporting, missing-number inference |
| `test_fingerprint.py` | 5 | stability, field sensitivity, per-entity scope |

### Coverage

| Scope | Coverage |
|---|---|
| Bolt-002 modules | **91%** |
| Whole `app/` | 80% (was 63% before this bolt's API tests) |

Clears the >80% criterion. The uncovered remainder is chiefly `importer/cli.py`, which is
argument parsing over an already-tested runner.

## The criterion that needed proving

> *Second run over unchanged sources: 0 added, 0 updated.*

Asserted against **the SQL actually issued**, not against the importer's own counters. That
distinction is the whole point: a naive `INSERT … ON DUPLICATE KEY UPDATE` with `updated_at` in
the UPDATE clause rewrites every row on every run while the counters cheerfully report zero —
busy and idempotent simultaneously. Only statement counting catches it.

`test_second_run_writes_nothing_to_the_catalog` measures **both** runs through the same filter.
The first run is the control: it must show catalog writes, otherwise an empty second run would
prove nothing but a broken filter. It then asserts the second issues none.

## Verified by execution

- `python -m app.importer --list` → `csv_seed (Curated CSV seed, offline)`, sets: `FE01`
- `app.main` imports; OpenAPI generates **7 operations across 5 paths**, the three new ones
  being `GET`/`POST /admin/catalog/imports` and `GET /admin/catalog/imports/{run_id}`
- Migration `0002` validated by generating its SQL offline (`alembic upgrade 0001:0002 --sql`):
  six tables, both unique constraints — including `uq_printings_natural_key` — and all indexes
- `ruff` reports **zero** `F8*`/`E7*` findings (undefined names, unused imports, syntax-class errors)

## Two bugs the checks caught

**1. A dropped import that four green test runs did not catch.** Extending
`core/dependencies.py` for the catalog wiring, the rewritten import block lost
`UserProfileRepository` — a name that file still uses in three places. Nothing failed:
`from __future__ import annotations` keeps annotations as strings, and FastAPI resolves them
leniently, so `/me` kept working by luck. `ruff`'s `F821` found it. It would have surfaced as a
`NameError` the moment anything called `get_type_hints` on that module.

**2. `source_ref` pointed at the wrong line.** `_rows` filtered comment lines *before* handing
the stream to `csv.DictReader`, so `reader.line_num` counted positions in the filtered stream.
A rejection saying `FE01.csv:12` would have sent an operator to the wrong row of a file whose
whole purpose is being hand-edited. Now the real line number is carried through the filter.

Also fixed while testing: the suite took **19s** because `log_event` opens its own session by
design, so every API request attempted a real MySQL connection and swallowed the failure.
Pointing it at the test database took the suite to **0.73s** — and removed hidden network I/O
from the whole suite, bolt 001's tests included.

## Not met — needs data entry, not code

**`One real set imported: every card, every printing, correct rarities` is NOT satisfied.**

`data/catalog/FE01.csv` ships with its header and no card rows. This is deliberate:

- ADR-001 rules out scraping the one complete source, and
- inventing 126 plausible-looking cards would put fabricated data in a catalog whose entire job
  is being correct.

So the set is *declared* at its printed size of 126 in `sets.csv`, and importing it succeeds
while reporting coverage **0/126** as a `warning`. That is the completeness guard working, and
it is exactly the state the guard was built to make visible rather than hide.

Closing this criterion needs someone to compile FE01 from cards they own and published
checklists. The importer, the schema, the rejection reporting and the idempotency are all
finished and tested; only the data is outstanding.


## Verified against real MySQL — 2026-08-11

The platform stack was already running (`../auth/docker-compose.yml`, 19 containers). Migrations
`0001`–`0003` applied to MySQL 8.4 cleanly, and `backend/scripts/verify_mysql.py` passed **24/24**
checks against it, `backend/scripts/bench.py` **5/5** NFR budgets. Both are re-runnable and clean
up after themselves.

What that closes for this bolt is listed below; anything still open stays listed as open.

| Was open | Now |
|---|---|
| Migration applied to real MySQL | ✅ `alembic upgrade head` clean on MySQL 8.4 |
| Full re-import < 15 minutes | ✅ **34.4s** for 5,000 cards / 7,500 printings |
| Idempotency under MySQL's own `ON DUPLICATE KEY UPDATE` | ✅ re-import reported 0 added, 0 updated, 5,000 unchanged |
| Behaviour under MySQL uniqueness enforcement | ✅ `uq_printings_natural_key` present and enforced |

**Still open:** the FE01 seed has no card rows, so "one *real* set imported" remains unmet. The
importer itself is now verified end to end against MySQL with synthetic data.

## Previously not verified — requires a running database

| Criterion | Why |
|---|---|
| Migration applied to real MySQL | Validated as generated SQL only; never run against a server |
| Full re-import < 15 minutes | Needs a full catalog to re-import |
| Behaviour under MySQL's own uniqueness enforcement | SQLite honours the constraints; MySQL's error surface differs |

Unit tests run on in-memory SQLite via `create_all`, exactly as `core/db.py` prescribes.
MySQL integration is a separate pass, unblocked the moment the platform is running.

## Deviations from the design, recorded

1. **A `sets.csv` registry was added** alongside the per-set files. The design said "one CSV per
   set"; `card_count` is the *printed* size and must be declared independently of the rows, so
   it needs a home that is not the card file. The per-set layout is otherwise as designed.
2. **Coverage compares distinct cards, not printings**, against `card_count`. Stage 1 said
   collector numbers and stage 2's NFR table said printings — the former is right, since 126
   cards can carry 189 printings and comparing those to 126 would report >100%.
3. **`set_codes` added to `catalog_imports`.** The run-detail response reports coverage for the
   sets a run touched, and `sets_seen` is only a count. Additive column in `0002`.
4. **`SetRepository.upsert` skips unchanged rows**, matching the rule already applied to cards
   and printings. Without it every re-import wrote every set row for nothing.
