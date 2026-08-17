---
id: 031-market-overview
unit: 006-price-surfaces
intent: 002-price-intelligence
status: complete
priority: should
created: 2026-08-15T15:00:00Z
assigned_bolt: 016-price-surfaces
implemented: true
---

# Story: 031-market-overview

## User Story

**As a** collector
**I want** a page showing what is moving across the whole game
**So that** I can see the market rather than only the cards I already own

## Acceptance Criteria

- [ ] **Given** `/prices`, **When** it loads, **Then** it shows top movers up and down, set indices,
      and most-traded items
- [ ] **Given** movers, **When** they are ranked, **Then** a printing needs a minimum observation
      count to appear, so a single odd sale cannot top the list
- [ ] **Given** an index, **When** it is shown, **Then** its definition is documented and its value
      reproducible from `price_daily`
- [ ] **Given** any figure on the page, **When** it renders, **Then** it carries its confidence and
      its observation count
- [ ] **Given** an anonymous visitor, **When** they load `/prices`, **Then** it works — this is a
      public page
- [ ] **Given** thin data across the board, **When** the page loads, **Then** it says the market is
      thinly covered rather than presenting a confident-looking list of noise

## Technical Notes

The minimum observation count is the difference between a market overview and a noise generator.
Without it the movers list is dominated by printings with one sale each, which is exactly the data
least worth ranking.

Indices need to be documented **and reproducible** — a "Base Set index" that nobody can recompute is
a number the site asserts rather than reports, which contradicts the intent's central promise.

Public, like the phase-1 catalog pages, and cacheable for the same reason: it does not vary by
caller.

## Dependencies

### Requires
- 019-price-daily-publication
- 030-card-price-tab — shares its chart components

### Enables
- Nothing downstream

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Not enough data for any mover to qualify | The section says so rather than lowering the bar |
| A set with almost no priced cards | Its index is unavailable, not zero |
| A card moves because a source was fixed | Indistinguishable from a real move on this page; the admin's source-agreement view is where that is caught |
| All movers from one source | Allowed but worth showing the source count per figure, which the confidence rule already requires |

## Out of Scope

- Personalised movers ("cards you own that moved") — that belongs on the portfolio
- Any editorial or predictive commentary
