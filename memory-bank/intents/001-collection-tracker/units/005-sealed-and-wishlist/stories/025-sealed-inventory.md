---
id: 025-sealed-inventory
unit: 005-sealed-and-wishlist
intent: 001-collection-tracker
status: complete
priority: must
created: '2026-08-09T12:00:00Z'
assigned_bolt: 007-sealed-and-wishlist
implemented: true
---

# Story: 025-sealed-inventory

## User Story

**As a** collector who buys boxes
**I want** to track sealed product separately from singles
**So that** my card counts stay honest and my sealed stock is still visible

## Acceptance Criteria

- [ ] **Given** I add sealed product, **Then** packs, boxes, starter decks, elite boxes, bundles and cases are all available with a quantity
- [ ] **Given** a holding exists, **Then** it records whether it is still sealed, plus cost basis, date and location
- [ ] **Given** I view `/collection` or any completion figure, **Then** sealed items appear in neither
- [ ] **Given** I mark a box as opened, **Then** a flag flips and **no singles are created**
- [ ] **Given** I export, **Then** sealed holdings appear as their own section
- [ ] **Given** I add the same product in the same sealed state twice, **Then** quantity increments

## Technical Notes

- Auto-generating singles from an opened box would invent data. The expected distribution is never the actual pull, so it would be wrong every time — and wrong in a way the user has to hunt down and correct.

## Dependencies

### Requires
- 007-catalog-schema
- 013-add-inventory-item

### Enables
- 027-csv-export

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Marking opened twice | Idempotent |
| Sealed product spanning sets | `set_id` is null; it still tracks |
| Opened box later re-sealed | Not modelled; the flag is one-way and that is stated |

## Out of Scope

- Valuing sealed product — intent 002
