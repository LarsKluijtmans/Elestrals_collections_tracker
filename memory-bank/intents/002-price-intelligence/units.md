---
intent: 002-price-intelligence
phase: inception
status: units-decomposed
updated: 2026-08-09T12:00:00Z
---

# Price Intelligence - Unit Decomposition

**6 units, 24 stories.** Stories are enumerated here and elaborated into individual files when this
intent enters construction.

---

### Unit 001: pipeline-infrastructure

**Description**: Move job execution from in-process APScheduler to Celery + Redis, with one queue
per source class, retries with backoff, run recording and a crashed-run sweeper. Plus the
`price_sources` registry and its legal gate.

**Stories**:
- 001-celery-redis-runtime
- 002-source-registry-and-legal-gate
- 003-run-lifecycle-and-sweeper
- 004-rate-limiting-and-politeness

**Deliverables**: Celery app, Redis, worker container joining the compose project;
`price_sources` + `scrape_runs` migrations; a `tos_review_note`-not-empty constraint on enablement;
per-source token-bucket limiter; honest user agent with contact address.

**Dependencies**: Depends on intent 001 unit 001. Depended by all other units here.
**Complexity**: M

---

### Unit 002: source-connectors

**Description**: One adapter per price source behind a single `PriceSource` contract — fetch recent
sold items, parse them, hand back raw observations. Prefer official APIs; scrape only where no API
exists and the terms allow it.

**Stories**:
- 005-source-contract
- 006-connector-official-api
- 007-connector-scrape
- 008-connector-fixtures-and-drift-detection

**Deliverables**: `pricing/sources/` with registered adapters; recorded HTTP fixtures per source;
a drift test that fails when a source's structure changes rather than silently returning nothing.

**Dependencies**: Depends on 001. Depended by 003.
**Complexity**: L — **the highest-uncertainty unit in the intent**, for the same reason the catalog
importer was in intent 001: it depends on third parties we do not control.

---

### Unit 003: matching-and-observations

**Description**: Resolve a listing title to a printing and a condition with a confidence, and record
it as an append-only observation with full provenance.

**Stories**:
- 009-title-to-printing-matcher
- 010-condition-extraction
- 011-observation-store-and-dedupe
- 012-sold-vs-listed-separation

**Deliverables**: `price_observations` migration; the matcher with a confidence floor that **rejects**
rather than guessing; `UNIQUE (source_id, external_id)` dedupe; every row keeping its `source_url`.

**Dependencies**: Depends on 002. Depended by 004.
**Complexity**: L — the matcher is the accuracy ceiling for everything downstream.

---

### Unit 004: rollups-and-valuation

**Description**: Aggregate observations into daily statistics, normalise currency, and value a
collection or any slice of it — always with coverage and confidence attached.

**Stories**:
- 013-daily-rollup-job
- 014-outlier-exclusion
- 015-fx-normalisation
- 016-collection-valuation
- 017-portfolio-history-and-pl
- 018-nightly-snapshot-valuation

**Deliverables**: `price_daily` + `fx_rates` migrations; IQR-based outlier exclusion; the valuation
service that **excludes and counts** unpriced items rather than treating them as zero; back-filling
`collection_snapshots` with values from the day phase 1 started recording counts.

**Dependencies**: Depends on 003, and on intent 001 unit 003. Depended by 005, 006.
**Complexity**: M

---

### Unit 005: price-surfaces

**Description**: Everything the user sees — the card price tab, the market overview, the portfolio,
and the value columns that attach to the phase-1 collection table.

**Stories**:
- 019-card-price-tab
- 020-market-overview
- 021-portfolio-page
- 022-slice-valuation

**Deliverables**: `/prices`, `/portfolio`, `/portfolio/slice`, the price tab on `/cards/:id`, value
and delta columns on `/collection`, `PriceSparkline` and `ConfidencePill` components; the dashboard
value tile finally showing a number instead of "available in phase 2".

**Dependencies**: Depends on 004.
**Complexity**: M

---

### Unit 006: alerts-and-ops

**Description**: Price alerts for users, and the operations console that keeps the pipeline honest.

**Stories**:
- 023-price-alerts
- 024-scraper-operations-console

**Deliverables**: `price_alerts` migration; alert evaluation in the rollup job with cooldown;
delivery through the phase-1 outbox; `/admin/scrapers` with per-source health, accept-rate trend,
ToS state and kill switch; an alert when a source's accept rate drops sustainedly.

**Dependencies**: Depends on 004, and on intent 001 unit 007 for the outbox.
**Complexity**: M

---

## Unit Dependency Graph

```text
[001 pipeline-infrastructure]
        └─> [002 source-connectors]
                  └─> [003 matching-and-observations]
                            └─> [004 rollups-and-valuation]
                                      ├─> [005 price-surfaces]
                                      └─> [006 alerts-and-ops]
```

Strictly serial until unit 004, because each stage consumes the previous stage's output. 005 and 006
then run in parallel.

## Execution Order

1. **001 pipeline-infrastructure** — nothing runs reliably without it
2. **002 source-connectors** — **opens with a spike**: which sources permit access to sold data, on
   what terms? Same risk posture as the catalog importer in intent 001
3. **003 matching-and-observations** — the accuracy ceiling for everything after it
4. **004 rollups-and-valuation** — the first point at which a number exists
5. **005 price-surfaces** — the first point at which a user sees one
6. **006 alerts-and-ops** — makes it operable and makes it push

## The one rule that governs this intent

**No figure renders without its confidence.** Coverage, observation count and window travel with
every number, from the valuation service through to the component props. A `low confidence` pill on
a rough number is worth more than a precise-looking figure a user cannot check — and once a user
catches one wrong confident number, they stop believing all of them.
