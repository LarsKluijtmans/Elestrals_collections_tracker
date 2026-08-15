---
id: 018-fx-normalisation
unit: 004-rollups-and-valuation
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 014-rollups-and-valuation
implemented: false
---

# Story: 018-fx-normalisation

## User Story

**As a** collector in the Netherlands
**I want** to see everything in euros without American sales silently changing value overnight
**So that** my collection's history reflects the market rather than the exchange rate

## Acceptance Criteria

- [ ] **Given** an observation in another currency, **When** it is converted, **Then** the rate used
      is the rate **for the observation's day**, not today's
- [ ] **Given** a converted figure, **When** it is shown, **Then** the original currency and amount
      remain visible on the sale record
- [ ] **Given** a day with no fetched rate, **When** conversion is needed, **Then** the previous
      day's rate is carried forward and the conversion is marked approximate
- [ ] **Given** the FX job, **When** it runs, **Then** it makes one call a day and stores rates in
      `fx_rates` keyed by day, base and quote
- [ ] **Given** a user's chosen currency, **When** any figure renders, **Then** it is converted
      consistently across every surface — no page mixes converted and unconverted figures

## Technical Notes

Using today's rate for a year-old sale rewrites history every morning: the same past day's value
changes because the euro moved, which makes a portfolio chart show movement that never happened.

`fx_rates` is `(day, base, quote) → rate`, and conversion is a join, not a call. The provider is
contacted once a day by a beat job; nothing in a request path talks to it.

Carry-forward is marked rather than silent, because an approximate conversion on a weekend is fine
and an approximate conversion for a fortnight is a broken job.

Money stays `*_cents BIGINT` plus an explicit currency throughout — standards §3. Conversion
produces a new amount and a new currency, never a float in between.

## Dependencies

### Requires
- 016-daily-rollup-job

### Enables
- 020-collection-valuation, 021-portfolio-history-and-pl
- Everything in unit 006 that renders money

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| FX provider is down for a day | Carry forward, mark approximate, log at `warning` |
| FX provider is down for a week | Still carries forward; the `warning` escalates. The figures remain usable and honestly labelled |
| A currency we have never seen appears | The observation is stored in its own currency; conversion is unavailable and the figure is excluded from converted views with a count, not treated as zero |
| User changes their currency | Every figure re-converts; nothing is cached in a user's currency |
| Historical backfill before our first rate | Conversion unavailable for those days; the chart starts where the rates do, and says so |

## Out of Scope

- Intraday rates
- Hedging or any notion of realised currency gain
