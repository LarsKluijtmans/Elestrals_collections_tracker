---
id: 008-import-export
unit: 006-import-export
intent: 001-collection-tracker
type: ddd-construction-bolt
status: planned
stories:
  - 027-csv-export
  - 028-csv-import-mapping
  - 029-csv-import-commit
created: 2026-08-09T12:00:00Z
started: null
completed: null
current_stage: null
stages_completed: []

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

- [ ] **1. model**: Pending → ddd-01-domain-model.md
- [ ] **2. design**: Pending → ddd-02-technical-design.md
- [ ] **3. implement**: Pending → `backend/app/services/import_export/`, `/import-export`
- [ ] **4. test**: Pending → ddd-03-test-report.md

## Dependencies

### Requires
- 004-inventory-core (writes go through `InventoryService`)
- 007-sealed-and-wishlist (export covers all three inventories)

### Enables
- Nothing. Leaf.

## Success Criteria

- [ ] Export → import: 0 adds, 0 updates, 0 rejects
- [ ] A mis-mapped column is caught in the dry run, before any write
- [ ] One bad row on line 900 → nothing committed
- [ ] Fuzzy matches never applied without per-row confirmation
- [ ] Exported values starting `= + - @` are prefixed with `'`
- [ ] 5,000-row dry run < 30s; 10,000-row export streams under 100MB RSS
- [ ] Fixtures for UTF-8-BOM, CP1252, semicolon-delimited and quoted-comma files
- [ ] Coverage > 80%

## Notes

**Build export first.** It defines the canonical format, and the round-trip is the strongest
correctness check available — it turns the import's matching ladder from speculation into something
testable on day one.

The matcher is the part that will take longer than it looks. Real collector spreadsheets have set
names instead of codes, `"Vipyro (Holo)"` in one column, quantities under a header called `#`, and
blank rows in the middle. The ladder in story 028 degrades honestly instead of guessing; hold that
line under schedule pressure, because a confident wrong match silently corrupts a collection that
someone has kept for years.
