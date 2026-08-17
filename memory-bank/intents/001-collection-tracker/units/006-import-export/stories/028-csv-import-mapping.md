---
id: 028-csv-import-mapping
unit: 006-import-export
intent: 001-collection-tracker
status: complete
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 008-import-export
implemented: true
---

# Story: 028-csv-import-mapping

## User Story

**As a** collector who already tracks a 3,000-card collection in Excel
**I want** to map my columns and see exactly what will change before anything happens
**So that** I can move to this product without risking the record I have kept for years

## Acceptance Criteria

- [ ] **Given** I upload a CSV, **When** it is parsed, **Then** delimiter and encoding are detected automatically — UTF-8, UTF-8-BOM and CP1252 all work, as do comma and semicolon delimiters
- [ ] **Given** the file is parsed, **When** the mapping step opens, **Then** a suggested column mapping is pre-filled and every mapping is editable
- [ ] **Given** I confirm the mapping, **When** the dry run completes, **Then** I see counts of rows to add, rows to update and rows rejected, with a per-row reason for every rejection
- [ ] **Given** the dry run has completed, **When** I inspect the database, **Then** **nothing has been written**
- [ ] **Given** rows matched only by fuzzy name, **When** the diff is shown, **Then** they are listed in a separate section and are **not** included unless I confirm them individually
- [ ] **Given** I mis-mapped quantity onto the collector-number column, **When** the dry run runs, **Then** the resulting nonsense is visible in the diff before I commit — this is the failure the dry run exists to catch
- [ ] **Given** I leave the page after the dry run, **When** I return later, **Then** the job is still there and still confirmable
- [ ] **Given** a file exceeds the size or row-count bound, **When** it is uploaded, **Then** it is rejected with a clear message rather than being partially processed

## Technical Notes

**The matching ladder**, most to least confident. Each rung records its own confidence, and the UI
treats them differently:

| Rung | Match on | Confidence | Applied without confirmation? |
|---|---|---|---|
| 1 | exact `printing_id` | high | yes — this is our own export round-tripping |
| 2 | `set_code` + `collector_number` + `finish` + `language` + `edition` | high | yes |
| 3 | `set_code` + `collector_number`, defaults applied | medium | yes, but flagged in the diff |
| 4 | fuzzy card name + set | low | **no — per-row confirmation required** |
| 5 | no match | — | rejected with a reason |

- Real collector spreadsheets are messy in specific, recurring ways: `"Vipyro (Holo)"` crammed into
  one name column, quantity in a column called `#`, missing collector numbers, set names instead of
  set codes, and blank rows in the middle. The suggested mapping should recognise the common header
  spellings; the ladder should degrade rather than guess.
- The job is persisted (`import_jobs` + `import_rows`) between mapping and commit. A 5,000-row dry
  run is not something to make someone sit through twice.
- Uploaded content is untrusted throughout: bounded size, bounded rows, no formula evaluation, and
  nothing from the file is ever interpolated into SQL or a log message unescaped.
- Fuzzy matching uses a normalised name (case-folded, punctuation stripped, parenthetical
  qualifiers extracted as finish hints) with a similarity floor — below the floor is a rejection,
  not a low-confidence match. A confident wrong match is worse than an honest failure.

## Dependencies

### Requires
- 027-csv-export (it defines the canonical format, and gives the round-trip test)
- 013-add-inventory-item (the service the commit writes through)

### Enables
- 029-csv-import-commit

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Empty file, or headers only | Rejected with "no data rows" |
| Duplicate rows for the same printing+condition | Summed in the diff and shown as one net change, so the preview matches the outcome |
| A row with quantity 0 | Rejected with a reason, not silently skipped |
| Encoding mis-detected, names contain mojibake | Preview shows the decoded names so the user can spot it before committing |
| Set code that does not exist | Rejected per row; the rest of the file still previews |
| 50,000-row file | Rejected against the row bound, with the bound stated |
| The same job confirmed twice | Second confirmation is a no-op; the job is idempotent by state |
| Cost basis column with mixed currencies | Rejected unless a currency column is mapped — a bare number is not money |

## Out of Scope

- The commit itself — `029-csv-import-commit`
- Importing from another tracker's API — a later intent if demand appears
- Image import
