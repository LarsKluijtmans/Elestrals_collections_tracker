---
id: 021-portfolio-history-and-pl
unit: 004-rollups-and-valuation
intent: 002-price-intelligence
status: complete
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 014-rollups-and-valuation
implemented: true
---

# Story: 021-portfolio-history-and-pl

## User Story

**As a** collector
**I want** to see how my collection's value has moved and whether I am up or down on what I paid
**So that** I can understand my collection as something that changes rather than a single number
today

## Acceptance Criteria

- [ ] **Given** `collection_snapshots` written since phase 1 launched, **When** the portfolio loads,
      **Then** value over time is drawn from them
- [ ] **Given** holdings with a cost basis, **When** P/L is computed, **Then** it covers exactly
      those holdings and the covered proportion is stated
- [ ] **Given** holdings without a cost basis, **When** P/L is computed, **Then** they are excluded
      and counted, never assumed to have cost zero
- [ ] **Given** the portfolio, **When** it renders, **Then** best and worst performers are listed
      with their contribution
- [ ] **Given** a period before any price data existed, **When** the chart renders, **Then** it
      starts where the data starts rather than showing a flat line at zero

## Technical Notes

Phase 1 has been writing `collection_snapshots` since launch precisely so this story does not begin
with an empty chart. Story 022 back-fills the *values* onto those existing count snapshots.

A cost basis is optional in phase 1's inventory, so partial coverage is the normal case, not an edge
case. Stating it is what keeps the number honest — an unrealised gain computed over a third of a
collection is a different claim from one computed over all of it.

Assuming zero cost for an unknown basis would report the entire market value as profit, which is
both wrong and flattering — the worst combination.

## Dependencies

### Requires
- 020-collection-valuation
- 022-nightly-snapshot-valuation — for history before today
- intent 001 / 003-inventory-core — cost basis fields

### Enables
- 032-portfolio-page

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| No cost basis anywhere | P/L unavailable, stated as such, with the value history still drawn |
| A holding sold or removed | It leaves the collection; history keeps the snapshots it was part of |
| Cost basis in another currency | Converted at the acquisition day's rate, per story 018 |
| A single day with a data gap | The line is broken at the gap rather than interpolated — an interpolated line invents a value |
| Best performer is an item with one observation | Shown with its observation count, so a thin data point is visibly thin |

## Out of Scope

- Realised P/L on items actually sold — phase 3 territory
- Tax reporting of any kind
