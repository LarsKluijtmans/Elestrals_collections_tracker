---
id: 009-light-scan
unit: 002-scrapers
intent: 002-price-intelligence
status: complete
priority: must
created: '2026-08-15T15:00:00Z'
assigned_bolt: 011-scraper-connectors
implemented: true
---

# Story: 009-light-scan

## User Story

**As an** admin
**I want** a cheap scan that re-checks what we already know and looks for new items next to it
**So that** listings that have gone are closed promptly and new arrivals are caught, without paying
for a full sweep every hour

## Acceptance Criteria

- [ ] **Given** known live listings, **When** a light scan runs, **Then** it re-checks them by id,
      oldest-looked-at first, up to a configured cap
- [ ] **Given** a listing still live, **When** it is re-checked, **Then** its price and `last_seen_at`
      are refreshed, and today's asking price is recorded
- [ ] **Given** a listing that has disappeared, **When** it is re-checked, **Then** it is marked
      ended and counted, and **no sale is recorded**
- [ ] **Given** the source could not be read at all, **When** the re-check fails, **Then** the
      listing is left alone — "I could not read it" is not "it is gone"
- [ ] **Given** the re-check has finished, **When** the neighbour plan is built, **Then** it targets
      products whose listing just ended, then products with no live listing, capped
- [ ] **Given** a light scan, **When** it completes, **Then** it has asked materially fewer queries
      than a deep scan and finished inside 20 minutes
- [ ] **Given** a scan that did not ask about a listing, **When** it finishes, **Then** that
      listing's `last_seen_at` is unchanged

## Technical Notes

The last criterion is the load-bearing one. `last_seen_at` moves **only** when a scan actually asked
about that listing; otherwise "gone" becomes indistinguishable from "not asked about since Tuesday",
and this whole story is built on that distinction.

Oldest-first is the fairness rule: it guarantees every tracked listing is eventually re-checked,
where newest-first would starve a long tail that never changes and is therefore never re-sorted.

The neighbour plan deliberately excludes products with several healthy live listings. The scan
already re-checks those by id; querying for more of what we are already tracking is the expensive
half of a deep scan with none of its discovery.

A light scan is **not** a shrunken deep scan. It never sweeps the catalog. Two questions only: are
the known listings still live, and did something new appear next to them.

## Dependencies

### Requires
- 007-source-connector-contract
- 008-deep-scan — there is nothing to re-check until a deep scan has found something

### Enables
- 015-sold-vs-listed-separation
- 026-run-history-and-health

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Source lists only active offers | A disappearance is `ended_unknown`. It may have sold, expired, been cancelled, been relisted, or been hidden from our region — and only one of those is a sale |
| Source reports the sale explicitly | `ended_sold` with the price, **only if** the source is configured as reporting sales (story 015) |
| Source is slow and the cap is not reached | The remainder is picked up next run, oldest-first, so nothing starves |
| A connector cannot re-check by id | Its re-check phase is skipped and the run says so, rather than silently verifying nothing |
| Every known listing has ended | Neighbour plan is large, which is correct: the market moved and that is when new listings appear |

## Out of Scope

- Discovering anything the deep scan's query space would find (story 008)
- Interpreting a disappearance as a sale — explicitly forbidden, see story 015
