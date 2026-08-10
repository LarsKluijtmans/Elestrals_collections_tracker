---
id: 027-csv-export
unit: 006-import-export
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 008-import-export
implemented: false
---

# Story: 027-csv-export

## User Story

**As a** collector
**I want** to download everything I have entered
**So that** choosing this product is not a lock-in decision

## Acceptance Criteria

- [ ] **Given** I export, **Then** singles, sealed and wishlist are all covered
- [ ] **Given** a filter is active on `/collection`, **Then** the export honours it
- [ ] **Given** the file is produced, **Then** it includes `printing_id` so a re-import matches exactly
- [ ] **Given** a value begins `=`, `+`, `-` or `@`, **Then** it is prefixed with `'` so the file cannot execute in a spreadsheet
- [ ] **Given** I export 10,000 rows, **Then** it streams without the server exceeding 100MB RSS
- [ ] **Given** the importer is documented, **Then** this exported file is the canonical format it describes

## Technical Notes

- **Build this before the importer.** It defines the format, and export→import round-tripping is the strongest correctness check available for the matcher.
- CSV injection is a real attack on the *user*, not on us: a crafted card note becomes a formula in their spreadsheet.

## Dependencies

### Requires
- 013-add-inventory-item
- 025-sealed-inventory

### Enables
- 028-csv-import-mapping
- 029-csv-import-commit

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Empty collection | Headers only, not an error |
| Notes containing commas, quotes or newlines | Properly quoted and round-trips |
| Non-ASCII card names | UTF-8 with BOM so Excel opens it correctly |

## Out of Scope

- Import — 028 and 029
