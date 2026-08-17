---
id: 012-title-to-printing-matcher
unit: 003-matching-and-observations
intent: 002-price-intelligence
status: complete
priority: must
created: '2026-08-15T15:00:00Z'
assigned_bolt: 012-matching-and-observations
implemented: true
---

# Story: 012-title-to-printing-matcher

## User Story

**As a** collector
**I want** a price only recorded against a card when we are actually sure which card it is
**So that** the valuation of my collection is not quietly wrong in a way nobody can detect
afterwards

## Acceptance Criteria

- [ ] **Given** a fully specified title (name, set, number, finish, edition), **When** it is
      matched, **Then** it resolves to exactly one printing above the confidence floor
- [ ] **Given** a title naming a card whose name contains another card's name, **When** it is
      matched, **Then** the longer name wins and no false ambiguity is reported
- [ ] **Given** a title with two different card names, **When** it is matched, **Then** confidence
      drops and the note says which second name was seen
- [ ] **Given** a graded slab (`PSA 10`, `BGS 9.5`, `slabbed`), **When** it is matched, **Then** it
      is refused with "graded" as the reason
- [ ] **Given** a multi-card lot (`3x`, `playset`, `bulk`, `lot of`), **When** it is matched, **Then**
      it is refused with the reason
- [ ] **Given** a proxy, custom or replica, **When** it is matched, **Then** it is refused
- [ ] **Given** a title in a language with no matching printing, **When** it is matched, **Then** it
      is refused — never folded onto the English printing
- [ ] **Given** a title with nothing to choose between several printings, **When** it is matched,
      **Then** the plainest is taken, confidence is penalised, and the result falls under the floor
- [ ] **Given** any refusal, **When** it is recorded, **Then** the listing is still stored with the
      reason in `match_note`
- [ ] **Given** a title matching nothing in the catalog, **When** it is matched, **Then** it is
      stored as unmatched and is reachable in one click from the explorer

## Technical Notes

The design commitment: **refuse rather than guess.** A matcher placing 95% of titles is worse than
one placing 60% if the extra 35% are wrong, because a wrong SKU is undetectable downstream.

Each refusal earns its place:

| Refusal | The failure it prevents |
|---|---|
| Graded | A PSA 10 and a raw copy are two markets; a slab price in a raw median inflates every valuation containing that card |
| Lot | "3x Vipyro at $30" is not a $30 Vipyro; dividing by a title-parsed quantity is arithmetic on a guess |
| Proxy | It is not the card |
| Wrong language | An English printing is not a cheaper Japanese card; it is a different card |

Scoring is deterministic with **named constants** — card name, set, collector number, stated
attributes, uniqueness, and penalties for ambiguity. Every weight is a constant so the calibration
can be tuned against story 028's accept-rate trend rather than by feel.

Two implementation notes that are easy to get wrong: the collector number must be read from the
**raw** title, because normalising the string removes the punctuation (`012/126`, `#012`) that the
number is made of; and card names should be bucketed by first word so matching a title tests a
handful of names rather than all 50,000.

## Dependencies

### Requires
- 008-deep-scan — listings to match
- intent 001 / 002-card-catalog — the printings to match *to*

### Enables
- 013-condition-extraction
- 014-observation-store-and-dedupe
- 025-listing-explorer — its most useful filter is "what could not be matched"

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Catalog is empty | Everything is unmatched, and the run says so loudly rather than reporting a 0% accept rate as normal |
| Title is another game's card | Unmatched, kept as a lead, no observation |
| Title is a sealed product not in our catalog | Recorded as a sealed lead — "candidate for the sealed catalog". This is one of the two things a deep scan is for |
| Seller writes the number without a set | Number narrows within whatever the name matched; often still under the floor, which is correct |
| Same card, two catalog entries | A catalog problem, surfaced by the explorer; the matcher does not silently pick one |

## Out of Scope

- Manually correcting a match — scoped out at Checkpoint 1
- Learning from corrections. Any ML here would make the one component that must be explainable
  unexplainable
