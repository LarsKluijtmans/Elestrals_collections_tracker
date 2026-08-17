---
id: 016-price-surfaces
unit: 006-price-surfaces
intent: 002-price-intelligence
type: ddd-construction-bolt
status: partial
stories:
  - 030-card-price-tab
  - 031-market-overview
  - 032-portfolio-page
  - 033-slice-valuation
created: 2026-08-15T15:25:00Z
started: 2026-08-15T15:30:00Z
completed: 2026-08-15T16:20:00Z
current_stage: done
stages_completed: [model, design, implement, test]

requires_bolts:
  - 014-rollups-and-valuation
  - 006-collection-browse
enables_bolts: []
requires_units: []
blocks: false

complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 2
---

# Bolt: 016-price-surfaces

## Overview

Everything a collector sees: the price tab on a card, the market overview, the portfolio, and the
value columns that finally give the phase-1 collection table and dashboard tile a number.

## Objective

**The first user-visible increment of the whole intent.** Nothing before this bolt is visible to a
collector, and under ADR-004 that is deliberate — scraped data gets judged before it gets shown.

## Stories Included

- **030-card-price-tab**: history, breakdown, and an honest empty state (Must)
- **031-market-overview**: movers that a single odd sale cannot top (Should)
- **032-portfolio-page**: value over time, and P/L where cost basis exists (Must)
- **033-slice-valuation**: value any filter of a collection (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. model**: Done → ddd-01-domain-model.md
- [x] **2. design**: Done → ddd-02-technical-design.md
- [x] **3. implement**: Done → `/prices`, `/portfolio`, card price tab, collection columns
- [x] **4. test**: Done → ddd-03-test-report.md

## Dependencies

### Requires
- 014-rollups-and-valuation (every figure on every page)
- 006-collection-browse (the table these columns attach to, and the filters 033 reuses)

### Enables
- Nothing. This is a leaf, and the product's payoff

## Success Criteria

- [ ] The price tab offers 30/90/365/all ranges, breaks down per condition and finish, and states
      each series' observation count
- [ ] No monetary figure renders without its confidence — enforced by `ConfidencePill` being a
      **required** prop, so a figure without one fails to compile
- [ ] A printing with no data shows an honest empty state, never a flat line at zero
- [ ] The price tab loads within 250ms p95, reading `price_daily` only
- [ ] Movers require a minimum observation count; indices are documented and reproducible
- [ ] `/prices` works for an anonymous visitor
- [ ] The portfolio states coverage ("412 of 500 items valued") and overall confidence
- [ ] Unpriced holdings are a **link**, not just a count
- [ ] P/L states the proportion of holdings that have a cost basis
- [ ] Slice filters are the *same implementation* as `/collection`, and a full-collection slice
      equals `/portfolio` — worth its own test
- [ ] The phase-1 dashboard tile shows a real number instead of "available in phase 2"
- [ ] No raw listing, match note or rejection reason reaches a non-admin
- [ ] Coverage > 80%

## Notes

The empty state matters more than it sounds. A chart drawn at zero reads as "this card is
worthless", which is a different and false claim from "we have not seen one sell".

Reuse `/collection`'s filter implementation for slices rather than writing a parallel one. Two
implementations over the same data model will disagree, and the disagreement surfaces as a valuation
that does not match the item list on screen — which reads as the valuation being broken.

This is where the auditability chain becomes user-visible: `price_daily` → `price_observations` →
`source_url`, through the recent-sales links. Under ADR-004 that chain is what makes the numbers
checkable rather than merely asserted.

## Construction result - 2026-08-15

**Status: partial.** Three of four stories, and the fourth is blocked on phase-1 work.

| Story | State |
|---|---|
| 030 card price tab | done - ranges, sold/asking toggle, per-point counts, honest empty state, inline sparkline |
| 031 market overview | done - `/prices`, public, movers gated on a minimum observation count |
| 032 portfolio page | **partial.** Current value, coverage, confidence and the unvalued breakdown are built; value-over-time needs `collection_snapshots` |
| 033 slice valuation | **not built.** It is specified as reusing `/collection`'s filters, and `/collection` does not exist yet - intent 001 bolt 006 is still `planned`. Writing a second filter implementation to fill the gap is exactly what the story says not to do |

`ConfidencePill` is a **required** prop on `MoneyFigure`, so a figure without its confidence fails
to compile. `test_renders_an_honest_empty_state_rather_than_a_zero` pins the other half: a printing
with no data shows "No sales seen", never a zero.

The sparkline is inline SVG rather than a charting dependency - one series, no axes; a library
would have been a larger commitment than the feature. Thin days are drawn as smaller points, so a
median built from one sale does not look as solid as one built from twenty.
