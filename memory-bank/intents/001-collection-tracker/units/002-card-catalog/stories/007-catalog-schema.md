---
id: 007-catalog-schema
unit: 002-card-catalog
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 002-card-catalog-schema-import
implemented: false
---

# Story: 007-catalog-schema

## Description

Migrations for `sets`, `cards`, `printings`, `sealed_products` and `catalog_imports` per `standards/data-model.md`.

## Rationale

`printings` is the SKU every later feature resolves through. Getting this grain wrong is the most expensive mistake available in the project.

## Acceptance Criteria

- [ ] **Given** the migration runs, **When** constraints are inspected, **Then** UNIQUE `(set_id, collector_number)` exists on cards and UNIQUE `(card_id, rarity, finish, language, edition)` on printings
- [ ] **Given** element and rune-type columns are inspected, **Then** the eight elements and five rune types are enumerated, not free text
- [ ] **Given** a set row is created, **Then** `card_count` holds the **printed** set size, independent of how many rows imported
- [ ] **Given** search is planned, **Then** indexes exist for prefix search on `cards.name` and for `(card_type, element)`
- [ ] **Given** the migration is rolled back, **Then** it reverses cleanly

## Technical Notes

- A collector owns a physical object: Vipyro, Base Set, Holo Rare, 1st Edition, English, Near Mint. Prices attach to that object, not to the name — hence three levels with `printings` as the join target.
- Condition lives on the holding, not the printing. The same printing in two conditions is one catalog row and two inventory rows.

## Dependencies

### Requires
- None — first schema in the domain

### Enables
- 008-catalog-importer
- and every story that references a card

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A card printed in two sets | Two `cards` rows — collector number is set-scoped |
| A printing with no rarity upstream | Rejected; rarity is part of the identity |
| Non-English printings | `language` is part of the unique key, so they coexist |

## Out of Scope

- Populating any of it — 008
