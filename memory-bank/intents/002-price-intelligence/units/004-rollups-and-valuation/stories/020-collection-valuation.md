---
id: 020-collection-valuation
unit: 004-rollups-and-valuation
intent: 002-price-intelligence
status: complete
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 014-rollups-and-valuation
implemented: true
---

# Story: 020-collection-valuation

## User Story

**As a** collector
**I want** to know what my collection is worth, and how much of it that number actually covers
**So that** I can trust the figure instead of wondering what it left out

## Acceptance Criteria

- [ ] **Given** a collection, **When** it is valued, **Then** the total is the sum over holdings of
      `quantity × median for that printing and condition`
- [ ] **Given** holdings with no price data, **When** the valuation runs, **Then** they are
      **excluded and counted separately**, never treated as zero
- [ ] **Given** a valuation, **When** it is returned, **Then** it states coverage — "412 of 500 items
      valued" — and an overall confidence
- [ ] **Given** a collection of 5,000 holdings, **When** it is valued, **Then** it returns within
      1.5s p95
- [ ] **Given** valuation, **When** it selects prices, **Then** it uses `sold` observations only
- [ ] **Given** a holding whose condition is not stated, **When** it is valued, **Then** it uses the
      rollup for that condition bucket, or is excluded and counted if there is none — never
      substituted with a different condition's price
- [ ] **Given** a graded holding, **When** it is valued, **Then** it is excluded and counted, because
      no graded prices are collected

## Technical Notes

Runs in `elestrals-api`, because it joins the user's inventory — which `harvest-api` cannot read and
should not. It reads `price_daily` through the story 019 grant.

"Excluded and counted, never zero" is the story's whole point. A zero for an unpriced holding
produces a total that is confidently wrong and silently low; a stated coverage produces a total that
is honestly partial. The second is usable and the first is not.

The graded exclusion follows from story 012's refusal: we deliberately collect no graded prices, so
a graded holding has no basis and saying so is correct.

## Dependencies

### Requires
- 019-price-daily-publication
- intent 001 / 003-inventory-core — the holdings

### Enables
- 021-portfolio-history-and-pl, 022-nightly-snapshot-valuation
- 033-slice-valuation

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Empty collection | Zero, with coverage 0 of 0, and an empty state rather than a currency symbol |
| No priced items at all | Total is stated as unavailable with coverage 0 of N — not a total of 0 |
| A printing priced in a currency with no rate | Excluded and counted, per story 018 |
| Holdings across many conditions | Each valued at its own condition's median |
| The most recent rollup is old | The valuation states the date of the data it used |

## Out of Scope

- Cost basis and P/L (story 021)
- Filters (story 033)
