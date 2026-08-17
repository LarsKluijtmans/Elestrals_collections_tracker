---
id: 015-sold-vs-listed-separation
unit: 003-matching-and-observations
intent: 002-price-intelligence
status: complete
priority: must
created: '2026-08-15T15:00:00Z'
assigned_bolt: 012-matching-and-observations
implemented: true
---

# Story: 015-sold-vs-listed-separation

## User Story

**As a** collector
**I want** what something sold for kept strictly apart from what someone is asking for it
**So that** my collection's value is built on transactions that happened, not on hopes

## Acceptance Criteria

- [ ] **Given** an observation, **When** it is written, **Then** its `sale_type` is exactly one of
      `sold` or `listed`, and the two are never combined in any figure
- [ ] **Given** a source not configured as reporting sales, **When** its connector claims a sale,
      **Then** the observation is recorded as `listed` and a warning is logged naming the
      disagreement
- [ ] **Given** a tracked listing that disappeared from a source that lists only active offers,
      **When** it is closed, **Then** it is `ended_unknown` and **no** `sold` observation is written
- [ ] **Given** a source that genuinely reports completed sales, **When** a sale is seen, **Then** a
      `sold` observation is written with the sale's own price and date
- [ ] **Given** a printing with only `listed` observations, **When** it is rolled up, **Then** its
      confidence is `low` by definition, regardless of how many there are
- [ ] **Given** valuation, **When** it computes, **Then** it reads `sold` only

## Technical Notes

**This is the requirement ADR-004 was taken to preserve.** The licensed feed in ADR-003 supplied
aggregate market prices — no sale count, no sale window, no comparables — and would have forced this
requirement to be weakened before construction. Scraped completed-listings pages carry the actual
price and the actual date. That is the technical case for the decision, and this story is where it
is cashed in.

The check is against `price_sources.reports_sold`, **not** against the connector's claim, and it
happens at the last moment before the write — where a wrong connector, a wrong config row and a
wrong test double all have to pass through it.

The asymmetry is deliberate: a source that reports sales may write both types; a source that does
not can never write `sold`. There is no configuration that makes a disappearance into a sale.

## Dependencies

### Requires
- 014-observation-store-and-dedupe
- 009-light-scan — where disappearances are detected

### Enables
- 016-daily-rollup-job
- 020-collection-valuation
- 034-price-alerts — which must never fire on `low` confidence

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| An auction ends with no bids | `ended_unsold` if the source says so, `ended_unknown` if it does not. Neither writes a sale |
| An auction ends with a winning bid | `sold` at the winning bid, if the source reports it |
| A best-offer sale at an undisclosed price | The listing ends; no `sold` observation, because we do not know the price. A sale with an unknown price is not a price observation |
| A listing is relisted at a new price | The old listing ends; the new one is discovered separately. No inference connects them |
| A connector is misconfigured as reporting sales | The config is authoritative. The failure mode is fabricated sales, so the review of that flag belongs with the terms review |

## Out of Scope

- Estimating a sale price for a sale we could not see
- Inferring sales from disappearances, under any heuristic. This is the line the whole story draws
