---
unit: 006-price-surfaces
intent: 002-price-intelligence
phase: inception
status: complete
created: '2026-08-15T14:55:00Z'
updated: '2026-08-17T23:55:00Z'
---

# Unit Brief: price-surfaces

## Purpose

Everything the collector sees. The price tab on a card, the market overview, the portfolio page, and
the value columns that finally give the phase-1 collection table and dashboard tile a number instead
of "available in phase 2".

Rollups only. No raw listing, no match note, no rejection reason ever reaches a non-admin — not as a
policy about secrecy, but because the raw data is uneven scraped material and presenting it to a
collector as a product would misrepresent what it is.

## Scope

### In Scope
- Price tab on `/cards/:id`: history chart, per-condition and per-finish breakdown, contributing
  sources, recent sales with links
- `/prices` market overview: top movers, set indices, most-traded
- `/portfolio`: value over time, cost basis versus market, P/L, best and worst performers
- `/portfolio/slice`: the same filters as `/collection`, applied to a valuation
- Value and delta columns on the phase-1 collection table; the dashboard value tile
- `PriceSparkline` and `ConfidencePill` components

### Out of Scope
- Computing any of it (unit 004)
- Alerts (unit 007)
- Anything admin-only (unit 005)

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-7 | Price history on a card | Must |
| FR-10 | Market overview | Should |
| FR-8 | The `/portfolio/slice` surface over unit 004's valuation | Must |
| FR-9 | The `/portfolio` surface over unit 004's history | Must |

---

## Domain Concepts

No new entities. Every view is a read of `price_daily` plus, for the portfolio,
`collection_snapshots` and `inventory_items`.

### Key Operations
| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `price_history(printing, range)` | The chart series | printing, 30/90/365/all | series + counts |
| `market_overview()` | Movers, indices, most-traded | window | ranked lists |
| `portfolio(user)` | Value over time and P/L | user, range | series + performers |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 4 |
| Must Have | 3 |
| Should Have | 1 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 030-card-price-tab | History, breakdown, and an honest empty state | Must | Planned |
| 031-market-overview | Movers that a single odd sale cannot top | Should | Planned |
| 032-portfolio-page | Value over time, and P/L where cost basis exists | Must | Planned |
| 033-slice-valuation | Value any filter of a collection | Must | Planned |

---

## Dependencies

### Depends On
| Unit | Reason |
|------|--------|
| 004-rollups-and-valuation | Every figure on every one of these pages |
| intent 001 / 004-collection-experience | The collection table these columns attach to, and the filters `/portfolio/slice` reuses |

### Depended By
| Unit | Reason |
|------|--------|
| — | Nothing. This is a leaf |

### External Dependencies
None.

---

## Technical Context

### Suggested Technology
React + MUI as phase 1. Charts from the project's existing charting choice; ranges 30/90/365/all as
a segmented control. `ConfidencePill` is a **required** prop on the money component — not optional,
so a figure without its confidence fails to compile rather than shipping.

### Integration Points
| Integration | Type | Protocol |
|-------------|------|----------|
| SPA → `elestrals-api` | API | REST `/api/v1/prices`, `/api/v1/portfolio` |

### Data Storage
None of its own.

---

## Constraints

- **No monetary figure renders without its confidence.** Standards §8, and it has teeth here.
- **An empty state is an empty state.** A printing with no data shows "no observations yet", never a
  flat line at zero — a chart at zero reads as "this card is worthless", which is a different and
  false claim.
- **Every series states its observation count.** A median from two sales and a median from two
  hundred are drawn the same way and mean very different things.
- **Movers need a minimum observation count** to appear, so one odd sale cannot top the list.
- **Reads hit `price_daily` only** — never the fact table, and never anything else in
  `elestrals_harvest`.
- p95 < 250ms on the price tab, which is achievable only because it reads rollups.
