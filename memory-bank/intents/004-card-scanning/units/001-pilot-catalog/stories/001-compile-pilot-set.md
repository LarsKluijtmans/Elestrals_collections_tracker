---
id: 001-compile-pilot-set
unit: 001-pilot-catalog
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T13:35:00Z'
assigned_bolt: 018-pilot-catalog
implemented: false
---

# Story: 001-compile-pilot-set

## User Story

**As** the person who has to make a scanner work
**I want** one complete Elestrals set present in the catalog
**So that** there is something for an identification to resolve *to* — today there is nothing, and
every other story in this intent quietly assumes otherwise

## Acceptance Criteria

- [ ] **Given** the pilot set's CSV, **When** the existing importer runs, **Then** it reports coverage
      as the full printed set size rather than as a warning
- [ ] **Given** a card with several printings, **When** its rows are compiled, **Then** the card-level
      fields repeat identically across those rows, and a disagreement rejects the card rather than
      letting row order decide
- [ ] **Given** the import, **When** it is re-run unchanged, **Then** it reports every card as
      `cards_unchanged` and issues no SQL, per the fingerprint behaviour bolt 002 built
- [ ] **Given** the compiled set, **When** `UNIQUE (set_id, collector_number)` is checked, **Then** no
      duplicate exists — the constraint is the assumption unit 003's matcher rests on
- [ ] **Given** the compiled set, **When** printings are counted, **Then** every distinct
      rarity/finish/language/edition combination that physically exists in the set has a row
- [ ] **Given** the importer, **When** this story completes, **Then** no importer, normaliser or schema
      code has changed

## Technical Notes

Rows go into `backend/data/catalog/{SET}.csv` in the shape the header already declares: one row per
**printing**, card-level fields repeated. The file's existing comment block explains the format and
the rule; it was written for exactly this moment.

Sources are cards physically owned plus publicly published checklists. **Not** `collect.elestrals.com`
— ADR-001 records that its Terms of Use prohibit both scraping and reproduction, and that decision is
not reopened by this intent.

The set is currently assumed to be FE01 because it is the file that exists. If another set is owned
more completely, that set is the better pilot, because story 002 requires photographing every printing
in it and a set you cannot physically complete produces a corpus with holes in it.

## Dependencies

### Requires
- intent 001 / story 008-catalog-importer (implemented)

### Enables
- 002-photograph-reference-set
- 011-catalog-index-for-devices — the index is built from these rows
- 009-reference-corpus-and-fingerprints

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A card's printing list is uncertain | Compile what is verifiable; record the uncertainty in the import notes rather than inventing a row. A fabricated printing is worse than a missing one because it can be matched to |
| The set's printed size disagrees with the checklist | The printed size is the completion denominator (`sets.card_count`); the discrepancy is recorded, not silently resolved |
| A printing exists that the CSV shape cannot express | **Stop.** This is a finding about the catalog schema and belongs in a decision record. Do not add an ad-hoc column |
| Compilation is only partly finished when the bolt needs to proceed | Acceptable for the spike (story 004), which needs ~20 cards. Not acceptable for this story to be called done |

## Out of Scope

- Any set beyond the pilot
- Card images — the `image_url` column stays empty here; images arrive via story 002 and, publicly,
  via story 022
