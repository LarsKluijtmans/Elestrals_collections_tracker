---
intent: 002-price-intelligence
phase: inception
status: complete
created: 2026-08-09T12:00:00Z
updated: 2026-08-09T12:00:00Z
---

# Requirements: Price Intelligence

## Intent Overview

Every day, gather what Elestrals items **actually sold for** across the internet, normalise those
sales onto our printings and sealed products, and turn them into three things a collector can act
on: a defensible price history per item, a valuation of their collection or any slice of it, and
alerts when something crosses a threshold they care about.

The product promise is narrow and deliberate: **we report observed sales, we do not set prices.**
Every figure carries how it was derived and how confident it is.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Coverage | ≥ 80% of *owned* printings have a sold observation in the last 7 days | Must |
| Trust | 100% of displayed values carry an observation count, a window and a confidence level | Must |
| Freshness | Daily run completes within its window ≥ 95% of days | Must |
| Usefulness | ≥ 50% of weekly-active users view `/portfolio` at least once a week | Should |
| Legality | 100% of enabled sources have a recorded ToS review and a robots check | Must |

---

## Functional Requirements

### FR-1: Source registry with a legal gate
- **Description**: Every price source is a configured row carrying its access mode, rate limit,
  weighting, robots-check date and a ToS review note.
- **Acceptance Criteria**: A source cannot be set `enabled = 1` while `tos_review_note` is empty;
  disabling a source takes effect on the next run with no deploy; official APIs are preferred over
  scraping wherever one exists.
- **Priority**: Must

### FR-2: Daily collection of sold prices
- **Description**: A scheduled job fetches recent **sold** items per source, with retries, backoff
  and per-source rate limiting.
- **Acceptance Criteria**: Each run is recorded in `scrape_runs` before work starts; a source
  failing does not fail the run for other sources; the run ends `success | partial | failed`; a
  crashed run is swept to `failed` rather than remaining `running` forever.
- **Priority**: Must

### FR-3: Match a sale to a printing
- **Description**: A matcher resolves a listing title to a `printing_id` (or `sealed_product_id`)
  plus a condition, recording a confidence.
- **Acceptance Criteria**: Matches below the confidence floor are rejected, not stored as
  low-confidence facts; `UNIQUE (source_id, external_id)` guarantees a re-run never double-counts;
  every observation retains its `source_url` so any figure is auditable back to origin.
- **Priority**: Must

### FR-4: Sold versus listed
- **Description**: Observations are typed as `sold` or `listed` and are never mixed.
- **Acceptance Criteria**: Valuation uses `sold` only; a `listed` price may be shown as "asking",
  clearly labelled; a printing with only `listed` data is `low` confidence by definition.
- **Priority**: Must

### FR-5: Daily rollups
- **Description**: A nightly job aggregates observations into `price_daily` (low, median, high,
  mean, counts, confidence) per printing, condition, day and currency.
- **Acceptance Criteria**: Charts and valuation read only `price_daily`, never the fact table;
  outliers beyond 3× the interquartile range are excluded from median and flagged; the rollup is
  rebuildable from observations.
- **Priority**: Must

### FR-6: Currency normalisation
- **Description**: Daily FX rates let a user see everything in their chosen currency.
- **Acceptance Criteria**: Conversion uses the rate for the observation's day, not today's; the
  original currency and amount remain visible on the sale record.
- **Priority**: Must

### FR-7: Price history on a card
- **Description**: The card detail page gains a price tab: history chart, per-condition and
  per-finish breakdown, contributing sources, and recent sales with links.
- **Acceptance Criteria**: Chart ranges 30/90/365 days and all-time; each series states its
  observation count; a printing with no data shows an honest empty state, not a flat line at zero.
- **Priority**: Must

### FR-8: Collection valuation
- **Description**: Value a whole collection, or any filtered slice of it.
- **Acceptance Criteria**: Valuation is the sum over holdings of `quantity × median for that
  printing and condition`; items with no data are **excluded and counted separately**, never
  treated as zero; the result states coverage ("412 of 500 items valued") and an overall
  confidence; the same filters as `/collection` apply.
- **Priority**: Must

### FR-9: Portfolio over time and P/L
- **Description**: Value history, cost basis versus market, and unrealized profit/loss.
- **Acceptance Criteria**: History is drawn from `collection_snapshots`, which phase 1 has been
  writing since launch; P/L is computed only over holdings that have a cost basis, and the covered
  proportion is stated; best and worst performers are listed.
- **Priority**: Must

### FR-10: Market overview
- **Description**: A public page of top movers, set indices and most-traded items.
- **Acceptance Criteria**: Movers require a minimum observation count to appear, so a single odd
  sale cannot top the list; indices are documented and reproducible.
- **Priority**: Should

### FR-11: Price alerts
- **Description**: A user sets a threshold on a printing, from the card page or a wishlist entry.
- **Acceptance Criteria**: Alerts fire at most once per cooldown window; delivery goes through
  notification-api via the phase-1 outbox; an alert states the price, the window and the confidence
  that triggered it; alerts never fire on `low` confidence data.
- **Priority**: Should

### FR-12: Scraper operations console
- **Description**: An RBAC-gated view of per-source health.
- **Acceptance Criteria**: Last run, duration, fetched/parsed/accepted/rejected, accept rate trend,
  ToS review state and a kill switch per source; a sustained drop in accept rate raises an alert.
- **Priority**: Must

---

## Non-Functional Requirements

### Performance
| Requirement | Metric | Target |
|---|---|---|
| Price history load | p95 | < 250ms (reads `price_daily` only) |
| Collection valuation, 5k holdings | p95 | < 1.5s |
| Daily collection run | wall clock | < 4 hours |
| Rollup job | wall clock | < 20 minutes |

### Scalability
| Requirement | Metric | Target (12-month) |
|---|---|---|
| `price_observations` | rows | 50M |
| `price_daily` | rows | 20M |
| Tracked printings | rows | 50,000 |

### Security & Conduct
| Requirement | Standard | Notes |
|---|---|---|
| Outbound | allowlisted hosts only | the scraper cannot be steered to arbitrary URLs |
| Identification | honest user agent + contact address | we are identifiable to every site we read |
| Rate | per-source limit, conservative by default | politeness is cheaper than a block |
| Data | no personal data collected from sources | prices, dates, titles and URLs only — never buyer or seller identity |
| Egress | no user data leaves | the scraper reads outward and writes inward, nothing else |

### Reliability
| Requirement | Metric | Target |
|---|---|---|
| Daily run success | rolling 30-day | ≥ 95% |
| Source isolation | one source failing | never fails another source's run |
| Rebuildability | rollups | fully regenerable from observations |

### Compliance
| Requirement | Standard | Notes |
|---|---|---|
| Source terms | per-source ToS review | recorded before enablement, re-reviewed annually |
| Financial framing | not investment advice | a visible disclaimer; we report observed sales, we do not advise |

---

## Constraints

**Intent-specific:**
- Jobs move from in-process APScheduler to **Celery + Redis** in this intent. Retries, isolation and
  queueing per source class are requirements here, not conveniences.
- `price_observations` is append-only. Corrections are new rows plus exclusion, never edits — a
  price history that can be silently rewritten is not evidence.
- No figure renders without its confidence. This is a UI rule with teeth: the `ConfidencePill` is a
  required prop on the money component, not an optional one.

---

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|---|---|---|
| At least two sources permit access to sold-price data | Coverage and confidence both collapse; the whole intent is decoration | The source registry is designed for churn; a single-source mode is honest but limited to `medium` confidence, and the UI says so |
| Listing titles carry enough signal to identify a printing | Matcher rejects most rows | Confidence floor with rejection rather than guessing; per-source title-parsing rules; manual mapping for high-value printings |
| Sold volume is high enough for a meaningful median | Most printings sit at `low` confidence | Honest confidence display is the mitigation — a sparse market shown truthfully still beats a fabricated number |
| Phase 1 has been writing `collection_snapshots` since launch | Portfolio history starts empty on the day phase 2 ships | Already handled: the snapshot table is built in phase 1 for exactly this reason |

## Open Questions

| Question | Owner | Due | Resolution |
|---|---|---|---|
| Which sources have an official API for sold data, and on what terms? | Lars | before unit 002 | **Pending** |
| Do we need a licensed data agreement to display aggregated prices commercially? | Lars | before phase 3 | **Pending** — matters much more once a marketplace charges fees |
| Median, or trimmed mean, as the headline figure? | Lars | during unit 003 | Leaning median with IQR outlier exclusion — resistant to the single silly sale, and explainable to a user |
