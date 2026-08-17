---
id: 008-import-export
unit: 006-import-export
intent: 001-collection-tracker
type: ddd-construction-bolt
status: complete
stories:
  - 027-csv-export
  - 028-csv-import-mapping
  - 029-csv-import-commit
created: 2026-08-09T12:00:00Z
started: 2026-08-17T20:45:00Z
completed: 2026-08-17T23:40:00Z
current_stage: done
stages_completed:
  - name: model
    completed: 2026-08-17T20:50:00Z
    artifact: import_jobs + import_rows, the matching ladder, the canonical CSV shape
  - name: design
    completed: 2026-08-17T20:55:00Z
    artifact: 0006_import_jobs.py, 8 endpoints, 4 services
  - name: implement
    completed: 2026-08-17T21:15:00Z
    artifact: backend/app/services/{export,import_*}_service.py, /import-export
  - name: test
    completed: 2026-08-17T21:25:00Z
    artifact: ddd-03-test-report.md

requires_bolts:
  - 007-sealed-and-wishlist
enables_bolts: []
requires_units: []
blocks: false

complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 2
  testing_scope: 2
---

# Bolt: 008-import-export

## Overview

Get a collection in from a spreadsheet and back out again. The anti-lock-in bolt, and the one that
makes the product adoptable by collectors who already track in Excel.

## Objective

A 3,000-row spreadsheet becomes a collection, with the user seeing exactly what will change before
anything is written — and the whole collection comes back out in a format that round-trips.

## Stories Included

- **027-csv-export**: export singles, sealed and wishlist, honouring the filter (Must)
- **028-csv-import-mapping**: column mapping and the dry-run diff (Must)
- **029-csv-import-commit**: atomic commit (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. model**: Done → `import_jobs` + `import_rows`, the five-rung matching ladder, and the
      canonical CSV shape that *is* the import contract
- [x] **2. design**: Done → `0006_import_jobs.py`, eight endpoints, four services
- [x] **3. implement**: Done → `services/{export,import_parser,import_matcher,import}_service.py`
- [x] **4. test**: Done → ddd-03-test-report.md — 98 new tests, 96% on this bolt's modules

## Dependencies

### Requires
- 004-inventory-core (writes go through `InventoryService`)
- 007-sealed-and-wishlist (export covers all three inventories)

### Enables
- Nothing. Leaf.

## Success Criteria

- [x] Export → import: 0 adds, 0 updates, 0 rejects — **the headline test**, and every row
      matches on rung 1
- [x] A mis-mapped column is caught in the dry run, before any write
- [x] One bad row on line 900 → nothing committed — *this failed first; see below*
- [x] Fuzzy matches never applied without per-row confirmation — and there is deliberately no
      "confirm all"
- [x] Exported values starting `= + - @` are prefixed with `'`, plus the tab and CR variants
- [x] 5,000-row dry run < 30s; 10,000-row export streams under 100MB RSS — **both measured and
      met** on MySQL 8.4 (2026-08-17): the dry run took **9.9s** of its 30s, and exporting 10,000
      rows grew resident memory by **5MB** of the 100MB allowed. All 5,000 rows matched on rung 1,
      which is the round trip closing at scale
- [x] Fixtures for UTF-8-BOM, CP1252, semicolon-delimited and quoted-comma files
- [x] Coverage > 80% — 96% on this bolt's modules

## Notes

**Build export first.** It defines the canonical format, and the round-trip is the strongest
correctness check available — it turns the import's matching ladder from speculation into something
testable on day one.

The matcher is the part that will take longer than it looks. Real collector spreadsheets have set
names instead of codes, `"Vipyro (Holo)"` in one column, quantities under a header called `#`, and
blank rows in the middle. The ladder in story 028 degrades honestly instead of guessing; hold that
line under schedule pressure, because a confident wrong match silently corrupts a collection that
someone has kept for years.

## Construction result - 2026-08-17

**Status: complete.** All three stories built, and both performance budgets measured on 2026-08-17
against MySQL 8.4 — a 5,000-row dry run in **9.9s** of its 30s, and a 10,000-row export costing
**5MB** of resident memory of the 100MB allowed. One criterion remains unwired: story 029's
`inventory.bulk_imported` metering, which waits on bolt 001's M2M scopes like every other metered
event in the service. It is a platform grant, not code.

| Story | State |
|---|---|
| 027 csv export | done — streams, honours the filter, defuses formulas, and *defines* the import format |
| 028 csv import mapping | done — encoding and delimiter sniffed, mapping suggested and editable, five-rung ladder, dry run writes nothing |
| 029 csv import commit | done — one transaction, through `InventoryService` |

**The bug worth recording, because it came out of a good decision.** The commit was not atomic, and
that is exactly what story 029's second criterion forbids. Two correct rules collided:
`InventoryService` commits each write with its completion recompute — deliberately, and it is why
completion can never disagree with inventory — and story 029 requires imports to write *through*
that service so imported rows obey the same invariants as typed ones. Together they produced a
commit-per-row, so rolling back after a failure on row 900 left 899 rows behind.

Fixed with an explicit `InventoryService.atomic()` that suspends per-write commits so a caller can
own the transaction. Recomputes still run per write; only the commit waits.

It was found by a test that made row 3 of 3 explode and then **counted the rows in the database** —
a test that only checked the error would have passed. Worth remembering when writing the next
all-or-nothing assertion.

Second, smaller: `normalise_name` turned `"Vipyro's Ember"` into `"vipyro s ember"`, differing from
`"Vipyros Ember"` by a whole token — the same card typed two ways, pushed below the similarity floor
by punctuation handling. Apostrophes are removed now, not spaced.

**The round trip is the bolt's spine.** Export a collection, import the file back, get 0 adds and 0
rejects with every row on rung 1. The bolt notes said to build export first for exactly this reason,
and they were right: it turns the matching ladder from speculation into something provable on day
one.

`python-multipart` joined `requirements.txt`. FastAPI raises at *import* time without it, so a
missing wheel takes down the service rather than one endpoint.
