---
unit: 002-scrapers
intent: 002-price-intelligence
phase: inception
status: complete
created: '2026-08-15T14:55:00Z'
updated: '2026-08-15T14:55:00Z'
---

# Unit Brief: scrapers

## Purpose

Read the sources. One contract, one connector per source, and two scan modes over them: **deep**,
which asks the whole catalog-derived query space and finds items never seen before, and **light**,
which re-checks known listings by id, closes the ones that have gone, and looks for new items near
the products whose market just moved.

This is the unit ADR-004 is about, and the unit most likely to be wrong. It depends on third parties
who have not agreed to be depended on, and the decision recorded in ADR-004 accepts that some of
them prohibit this and may block us for it. Two of its five stories exist only because of that:
drift detection, because a scraper that breaks silently returns zero rows and a quiet market also
returns zero rows; and quarantine, because a pipeline that retries into a block makes the block
worse.

## Scope

### In Scope
- The connector contract: `describe()`, `discover(query)`, `recheck(ids)`
- Per-source connectors, registered rather than imported ad hoc
- `market_listings`: one row per offer, tracked across its whole life, with a four-value status
- The deep planner (catalog → queries, broadest first, capped and ordered)
- The light planner (known listings + neighbours of products whose market moved)
- Recorded HTTP fixtures per connector and a drift test that fails loudly
- Block detection: sustained 403/429/challenge → quarantine, backoff, single probing retry

### Out of Scope
- Turning a title into a printing (unit 003) — this unit hands back raw listings
- Rollups, valuation, anything a user sees (units 004, 006)
- The console that displays run health (unit 005) — this unit emits the numbers, it does not draw
  them

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-2 | Two scan modes, deep and light | Must |
| FR-18 | Survive being blocked | Must |

---

## Domain Concepts

### Key Entities
| Entity | Description | Attributes |
|--------|-------------|------------|
| MarketListing | An offer we have seen, tracked over its life | `source_id`, `external_id`, `title`, `url`, `price_cents`, `currency`, `status`, `first_seen_at`, `last_seen_at`, `ended_at` |
| Query | One question to ask a source, and why | `text`, `reason`, `kind_hint`, `scope` |
| RawListing | One offer as the source described it, before matching | `external_id`, `title`, `url`, `price_cents`, `currency`, `observed_at`, `is_sold` |
| ListingState | What a re-check learned about one known listing | `external_id`, `status`, `price_cents` |

### Key Operations
| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `deep_plan(catalog)` | The whole query space, broadest first | catalog index, cap | ordered queries |
| `light_plan(focuses)` | Neighbours of products whose market moved | focus list, cap | ordered queries |
| `discover(query)` | Ask a source a question | query, limit | raw listings |
| `recheck(ids)` | Are these specific offers still live? | external ids | listing states |
| `quarantine(source)` | Stop asking, and record why | source, reason | quarantine until |

### Listing status machine

```text
active ─┬─> ended_sold       the source told us it sold
        ├─> ended_unsold     the source told us it ended without a sale
        └─> ended_unknown    it was live, now it is gone, and nobody said why
             └─> active      relisted; the end is withdrawn with it
```

`ended_unknown` is the honest majority case for any source that lists only active offers. A source
may only produce `ended_sold` when it genuinely reports completed sales, checked against its
configuration rather than its connector's claim.

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 5 |
| Must Have | 5 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 007-source-connector-contract | One contract, one file per source | Must | Planned |
| 008-deep-scan | Find what we have never seen | Must | Planned |
| 009-light-scan | Re-check the known, find the neighbours | Must | Planned |
| 010-connector-fixtures-and-drift-detection | Fail loudly when a source changes | Must | Planned |
| 011-block-detection-and-quarantine | Survive being blocked | Must | Planned |

---

## Dependencies

### Depends On
| Unit | Reason |
|------|--------|
| 001-harvest-service | The service, the registry, the gate, the rate limiter |
| intent 001 / 002-card-catalog | The deep planner builds its queries from the catalog |

### Depended By
| Unit | Reason |
|------|--------|
| 003 | There is nothing to match until there are listings |
| 005 | The console displays this unit's runs and listings |

### External Dependencies
| System | Purpose | Risk |
|--------|---------|------|
| Scraped marketplaces and storefronts | every price in the product | **High** — structure changes without notice, terms prohibit this on at least two of them, and blocks are expected rather than exceptional (ADR-004) |

---

## Technical Context

### Suggested Technology
`httpx` with `follow_redirects=False` and the per-source bucket from unit 001. HTML parsing with
`selectolax` where a source serves HTML; JSON straight through where it serves JSON. Fixtures are
recorded responses committed to the repo, replayed by the drift test — not live calls in CI.

### Integration Points
| Integration | Type | Protocol |
|-------------|------|----------|
| External sources | outbound scrape | HTTPS, allowlisted hosts, no off-host redirects |
| `elestrals` catalog | inbound read | MySQL cross-schema, read-only |

### Data Storage
| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| `market_listings` | SQL | 2M at 12 months | permanent; ended rows kept as history |

---

## Constraints

- **A disappearance is not a sale.** A listing that vanishes from a source that lists only active
  offers becomes `ended_unknown`, never `ended_sold`. Recording it as a sale manufactures a
  transaction that may not have happened, and FR-4 builds valuation on `sold`.
- **`last_seen_at` moves only when a scan actually asked about that listing.** Otherwise "gone"
  becomes indistinguishable from "not asked about lately", and the light scan is built entirely on
  that distinction.
- **One query failing fails that query.** A run that answers 380 of 400 questions is `partial`, not
  `failed` — reporting it as failed trains everyone to ignore the status.
- **Plans are capped and ordered, and truncation is visible.** The broadest queries are generated
  first so a truncated plan still discovers; `harvest_runs.queries` records what actually ran.
- **Quarantine is a state of the source, not a decision each run makes.** A blocked source stops
  being asked until the backoff expires.
