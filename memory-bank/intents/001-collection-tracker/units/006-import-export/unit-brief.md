---
unit: 006-import-export
intent: 001-collection-tracker
phase: inception
status: stories-defined
created: '2026-08-09T12:00:00Z'
updated: '2026-08-09T12:00:00Z'
---

# Unit Brief: import-export

## Purpose

Let a collector bring an existing collection in from a spreadsheet, and take everything back out.
This is the unit that makes the product adoptable by the many collectors who already track in Excel,
and the unit that means choosing it is not a lock-in decision.

## Scope

### In Scope
- CSV export of singles, sealed and wishlist, honouring the active filter
- Two-step import: upload + column mapping, then a **dry-run diff** the user confirms
- The matcher that resolves a spreadsheet row to a `printing_id`
- Atomic commit — an import applies fully or not at all
- CSV-injection neutralisation on export; untrusted-input handling on import
- `/import-export` page

### Out of Scope
- Importing from another tracker's API (a later intent if demand appears)
- Image import
- Scheduled/recurring import

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-13 | CSV import and export | Must |

---

## Domain Concepts

### Key Entities
| Entity | Description | Attributes |
|--------|-------------|------------|
| ImportJob | One upload through to commit | `user_sub`, `filename`, `column_map`, `state`, counts |
| ImportRow | One parsed line and its resolution | raw values, `printing_id` or rejection reason, `match_confidence` |
| ColumnMap | User-confirmed mapping of CSV headers to fields | header → field |

### Key Operations
| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `parse` | Read CSV, sniff delimiter and encoding | file | rows + detected headers |
| `suggest_map` | Guess the column mapping | headers | proposed map |
| `resolve` | Match a row to a printing | row, map | printing id + confidence, or rejection |
| `dry_run` | Produce the diff without writing | job | adds / updates / rejects |
| `commit` | Apply atomically | job | summary |
| `export` | Serialise the active filter | `sub`, filters | CSV stream |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 3 |
| Must Have | 3 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 027-csv-export | Export my collection | Must | Planned |
| 028-csv-import-mapping | Map columns and preview the diff | Must | Planned |
| 029-csv-import-commit | Commit an import atomically | Must | Planned |

---

## Dependencies

### Depends On
| Unit | Reason |
|------|--------|
| 003-inventory-core | Writes go through its services so invariants hold |
| 005-sealed-and-wishlist | Export covers all three inventories |

### Depended By
| Unit | Reason |
|------|--------|
| — | Leaf |

### External Dependencies
None. Deliberately — an import must work offline of every third party.

---

## Technical Context

### Suggested Technology
Python `csv` with delimiter and encoding sniffing (UTF-8, UTF-8-BOM and CP1252 all occur in the
wild). Streamed export so a 10k-row download does not materialise in memory. The import job is
persisted between the mapping and commit steps so a user can walk away and come back.

**Matching ladder**, most to least confident:
1. Exact `printing_id` (our own export round-tripping)
2. `set_code` + `collector_number` + `finish` + `language` + `edition`
3. `set_code` + `collector_number` (defaults applied, confidence `medium`)
4. Fuzzy card name + set (confidence `low`, **always requires per-row confirmation**)
5. No match → rejection with a reason

### Integration Points
| Integration | Type | Protocol |
|-------------|------|----------|
| Our API | REST | `/api/v1/import`, `/api/v1/export` |

### Data Storage
| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| `import_jobs` + `import_rows` | SQL | transient | purged 7 days after commit or abandonment |

---

## Constraints

- **Nothing is written before the user confirms the diff.** The dry run is not optional and not
  skippable — a bad column map silently duplicating a 3,000-card collection is unrecoverable in
  practice, whatever the undo story claims.
- The commit is one transaction. Partial imports do not exist.
- Uploaded CSV is untrusted input: bounded size, bounded row count, no formula evaluation, and
  values beginning `= + - @` are prefixed with `'` **on export** so a downloaded file cannot execute
  in the user's spreadsheet.
- Import writes through `InventoryService`, never straight to the repository, so merge-on-duplicate
  and completion recomputation apply identically to imported and hand-entered rows.
- Export round-trips: exporting and re-importing must produce zero changes.

---

## Success Criteria

### Functional
- [ ] Export → import produces a diff of 0 adds, 0 updates, 0 rejects
- [ ] A mis-mapped column is caught in the dry run, before any write
- [ ] A file with one bad row on line 900 commits nothing
- [ ] Rejections list the row number and a human-readable reason
- [ ] Fuzzy matches are never applied without per-row confirmation
- [ ] Export honours the collection filter that was active

### Non-Functional
- [ ] 5,000-row import dry run completes in < 30s
- [ ] 10,000-row export streams without exceeding 100MB RSS
- [ ] A cell containing `=cmd|'/c calc'!A1` is inert in the exported file

### Quality
- [ ] Fixture files for UTF-8-BOM, CP1252, semicolon-delimited and quoted-comma cases
- [ ] Code coverage > 80%
- [ ] Code reviewed and approved

---

## Bolt Suggestions

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| 008-import-export | DDD | 027, 028, 029 | Export first (it defines the canonical format), then the matcher, then the two-step import |

---

## Notes

Build **export before import**. The exported file is the reference format, the round-trip test is
the strongest correctness check available here, and having it first makes the import's matching
ladder concrete instead of speculative.

The matcher is the deceptively hard part. Budget for it: real collector spreadsheets have merged
sets, missing collector numbers, `"Vipyro (Holo)"` in a single name column, and quantities in a
column called `#`. The ladder above degrades honestly rather than guessing confidently.
