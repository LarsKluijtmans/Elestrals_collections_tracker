---
id: 029-csv-import-commit
unit: 006-import-export
intent: 001-collection-tracker
status: complete
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 008-import-export
implemented: true
---

# Story: 029-csv-import-commit

## User Story

**As a** collector
**I want** an import to either fully apply or not happen
**So that** a bad file never leaves my collection half-changed

## Acceptance Criteria

- [ ] **Given** I confirm a dry run, **Then** the commit runs as a single transaction
- [ ] **Given** one row on line 900 is bad, **Then** nothing is written at all
- [ ] **Given** rows are written, **Then** they go through `InventoryService`, so merge-on-duplicate and completion recompute apply identically to imported and hand-entered rows
- [ ] **Given** the commit finishes, **Then** the summary states exactly what was added and updated
- [ ] **Given** I export then re-import, **Then** the diff is 0 adds, 0 updates, 0 rejects
- [ ] **Given** a commit succeeds, **Then** `inventory.bulk_imported` is metered with the row count and the import id as `reference_1`
- [ ] **Given** a file is uploaded, **Then** its size and row count are bounded and it is treated as untrusted throughout

## Technical Notes

- Writing through the service rather than the repository is what stops imported data from bypassing the invariants that hand-entered data obeys.

## Dependencies

### Requires
- 028-csv-import-mapping
- 013-add-inventory-item

### Enables
- Adoption by collectors who already track elsewhere

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Transaction deadlock on a large import | Retried once, then failed cleanly with nothing written |
| Commit of an already-committed job | No-op; the job is idempotent by state |
| Import that would exceed a per-user row cap | Rejected before the transaction opens |

## Out of Scope

- Mapping and the dry run — 028
