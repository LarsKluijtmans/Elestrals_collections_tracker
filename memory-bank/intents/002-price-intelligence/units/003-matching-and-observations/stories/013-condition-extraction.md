---
id: 013-condition-extraction
unit: 003-matching-and-observations
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 012-matching-and-observations
implemented: false
---

# Story: 013-condition-extraction

## User Story

**As a** collector
**I want** a Near Mint price and a Heavily Played price kept apart
**So that** the value of my Near Mint copy is not dragged down by somebody else's damaged one

## Acceptance Criteria

- [ ] **Given** a title containing a condition in words or in a standard abbreviation, **When** it is
      matched, **Then** the condition resolves to one of the six catalog conditions
- [ ] **Given** "near mint" and "mint" in the same title, **When** it is read, **Then** "near mint"
      wins — the longer phrase is checked first
- [ ] **Given** a two-letter abbreviation (`nm`, `lp`, `mp`, `hp`), **When** it is read, **Then** it
      matches only as a whole word, so it cannot match inside another word
- [ ] **Given** a title stating no condition, **When** it is matched, **Then** the condition is null
      rather than defaulted — an unstated condition is unknown, not Near Mint
- [ ] **Given** a sealed product, **When** it is matched, **Then** no condition is recorded
- [ ] **Given** a condition that does not map to our six, **When** it is read, **Then** it is
      recorded as null rather than approximated to the nearest one

## Technical Notes

Reuses the phase-1 condition vocabulary (`CONDITIONS` on the inventory model) rather than defining a
second one — two vocabularies for the same concept will disagree, and the one that disagrees is
whichever was updated last.

A null condition is a real and common answer. Rollups group by condition and treat null as its own
bucket; guessing Near Mint because most cards are Near Mint would bias every median upward, and
sellers who do not state a condition are disproportionately selling played cards.

Graded cards do not reach this step — story 012 refuses them before condition is considered, because
a grade is not a condition and the schema has nowhere to put it.

## Dependencies

### Requires
- 012-title-to-printing-matcher

### Enables
- 014-observation-store-and-dedupe
- 016-daily-rollup-job — which groups by condition

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| "NM/M" | Near Mint. The better half of a range is not assumed; the first matching phrase wins and the tables are ordered accordingly |
| "Excellent", "EX" | Null. It is not one of our six, and mapping it to Lightly Played would be a guess with a price attached |
| Condition in a non-English word | Null, unless the connector's source is known to use it and maps it explicitly |
| "Mint condition box" on a sealed product | Ignored — sealed products carry no condition |
| Two conditions in one title | The first match by the table's order; ambiguity here is far less costly than in the SKU |

## Out of Scope

- Grading (refused upstream)
- Inferring condition from a photo
