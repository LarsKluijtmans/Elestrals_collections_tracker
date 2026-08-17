---
id: 013-add-inventory-item
unit: 003-inventory-core
intent: 001-collection-tracker
status: complete
priority: must
created: '2026-08-09T12:00:00Z'
assigned_bolt: 004-inventory-core
implemented: true
---

# Story: 013-add-inventory-item

## User Story

**As a** collector
**I want** to record that I own a specific printing in a specific condition
**So that** my collection reflects the physical cards in my binder

## Acceptance Criteria

- [ ] **Given** I am signed in and viewing a printing, **When** I add it with a condition and a quantity of 1, **Then** a holding is created and my set completion updates without a page refresh
- [ ] **Given** I already own 2 copies of a printing in Near Mint, **When** I add 1 more of the same printing and condition, **Then** I have one row with quantity 3 — not a second row
- [ ] **Given** I own an ungraded copy of a printing, **When** I add a PSA 10 copy of the same printing, **Then** a **separate** row is created, because a graded copy is individually identified
- [ ] **Given** I submit a quantity of 0 or a negative number, **When** the request is validated, **Then** it is rejected with a 422 and no row is touched
- [ ] **Given** I supply a `printing_id` that does not exist, **When** I submit, **Then** I get a 404 and no row is created
- [ ] **Given** I am adding, **When** I optionally supply cost basis, acquisition date, storage location, notes or a for-trade flag, **Then** all of them persist against the holding
- [ ] **Given** two identical add requests arrive within milliseconds of each other, **When** both are processed, **Then** the result is one row with the summed quantity — verified under real concurrency, not sequentially
- [ ] **Given** an add succeeds, **When** the transaction commits, **Then** `inventory.item_added` is metered with my `sub` as subject, the quantity added, and the set code as `reference_1`
- [ ] **Given** metering or forwarding fails, **When** the add completes, **Then** the add still succeeds

## Technical Notes

- `user_sub` comes from the validated JWT `sub`. There is **no** code path where it is read from the
  request body or a query parameter.
- Merge-on-duplicate is implemented as `INSERT ... ON DUPLICATE KEY UPDATE quantity = quantity + :n`
  against the unique constraint. A read-then-write in the service layer passes every sequential test
  and loses rows under the concurrency the fast-add flow actually produces.
- The uniqueness key covers ungraded holdings only. Graded rows are exempted in `InventoryService`,
  not by relaxing the constraint — the constraint stays strict and graded rows carry a distinct
  discriminator.
- Completion recompute runs inside the same transaction. If it fails, the add rolls back; the two
  must never disagree.
- Repository signature is `add_item(user_sub: str, ...)` — subject first and required, so an
  unscoped call cannot be written.

## Dependencies

### Requires
- 007-catalog-schema (there must be a printing to point at)
- 004-app-logging

### Enables
- 014-edit-inventory-item
- 015-remove-inventory-item
- 016-fast-add-flow
- 023-set-completion
- 029-csv-import-commit

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Same printing, different condition | Separate rows — condition is part of the identity |
| Same printing and condition, one graded one not | Separate rows |
| Two PSA 10 copies of the same printing | Separate rows; graded copies are individually meaningful |
| Quantity above a sane bound (e.g. 100,000) | Rejected with 422; a plausible ceiling beats an integer overflow later |
| Add while the printing is deleted by an importer run mid-request | Foreign key rejects; 404 returned; catalog rows are soft-retired rather than deleted for this reason |
| Cost basis given without a currency | Rejected — a bare number is not money |
| Cost basis omitted entirely | Accepted; phase-2 P/L treats basis as unknown, never as zero |

## Out of Scope

- The add *UI* — that is 016-fast-add-flow and 017-set-grid-entry
- Sealed product — 025-sealed-inventory
- Any valuation of the added card — intent 002
