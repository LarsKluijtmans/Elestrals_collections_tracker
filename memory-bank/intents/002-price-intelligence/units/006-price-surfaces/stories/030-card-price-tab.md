---
id: 030-card-price-tab
unit: 006-price-surfaces
intent: 002-price-intelligence
status: complete
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 016-price-surfaces
implemented: true
---

# Story: 030-card-price-tab

## User Story

**As a** collector
**I want** to see what a card has been selling for
**So that** I can decide what to pay for one, or what mine is worth

## Acceptance Criteria

- [ ] **Given** a card with price data, **When** I open its price tab, **Then** I see a history chart
      with ranges 30, 90, 365 days and all-time
- [ ] **Given** the tab, **When** it renders, **Then** prices break down per condition and per finish
- [ ] **Given** any series, **When** it renders, **Then** it states its observation count
- [ ] **Given** any figure, **When** it renders, **Then** it carries its confidence
- [ ] **Given** a printing with no data, **When** I open its tab, **Then** it shows an honest empty
      state — never a flat line at zero
- [ ] **Given** the tab, **When** it loads, **Then** it returns within 250ms p95, reading
      `price_daily` only
- [ ] **Given** recent sales, **When** they are listed, **Then** each links to its source
- [ ] **Given** a card with only asking-price data, **When** it renders, **Then** the figures are
      labelled as asking prices and carry `low` confidence

## Technical Notes

The empty state matters more than it sounds. A chart drawn at zero reads as "this card is
worthless", which is a different and false claim from "we have not seen one sell".

Every series stating its count is the phase-2 design commitment made visible: a median from two
sales and a median from two hundred are drawn identically and mean very different things.

`ConfidencePill` is a **required** prop on the money component, so a figure without its confidence
fails to compile rather than shipping. Standards §8.

The recent-sales links are the user-facing end of the auditability chain — `price_daily` →
`price_observations` → `source_url`. Under ADR-004 that chain is what makes the numbers checkable
rather than merely asserted.

## Dependencies

### Requires
- 019-price-daily-publication
- intent 001 / 002-card-catalog — the card detail page this tab joins

### Enables
- 031-market-overview shares its chart components

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Card has several printings, only one priced | Each printing shows its own state; the priced one is not presented as the card's price |
| Data exists but only outside the selected range | "No sales in this period", with the range still selectable |
| Only one observation ever | Drawn as a point with count 1 and `low` confidence |
| Rollup has not run today | Shows the most recent day it has, dated |
| A source was later disabled | Its historical observations remain; history is not rewritten by config |

## Out of Scope

- Raw listings, match notes, rejection reasons — admin-only
- Price predictions of any kind
