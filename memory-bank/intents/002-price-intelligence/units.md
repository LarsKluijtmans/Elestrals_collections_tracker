---
intent: 002-price-intelligence
phase: inception
status: units-decomposed
updated: 2026-08-15T14:50:00Z
---

# Price Intelligence - Unit Decomposition

**7 units, 34 stories.** Re-cut on 2026-08-15 for ADR-004 and the second-backend decision. The
previous cut had 6 units and 24 stories against a single backend and a licensed feed.

## What changed and why

| Before | After | Reason |
|---|---|---|
| 001 `pipeline-infrastructure` (in the existing backend) | **001 `harvest-service`** | The pipeline now *is* a service. Its schema, grants, container and release path are the unit's first deliverables, not incidental to them |
| 002 `source-connectors` | **002 `scrapers`** | Two scan modes are now first-class, and block survival (FR-18) is a story rather than an assumption |
| — | *(new stories inside 002)* | Quarantine exists only because of ADR-004 |
| 006 `alerts-and-ops` | split → **005 `admin-console`** and **007 `alerts`** | The ops console grew from one story into the primary surface of the intent. Alerts are unrelated work that was sharing a unit with it for no reason |
| — | **005 `admin-console`** | FR-14 to FR-17 are new |

Stories are elaborated as individual files under `units/{unit}/stories/`.

---

### Unit 001: harvest-service

**Description**: The second backend itself. A deployable FastAPI service owning the
`elestrals_harvest` schema, with its own Alembic tree and its own MySQL user; Celery + Redis for
out-of-band work; the source registry with its recorded-risk gate; run lifecycle and the crashed-run
sweeper; per-source rate limiting and identification.

**Stories**:
- 001-harvest-service-skeleton
- 002-harvest-schema-and-grants
- 003-celery-redis-runtime
- 004-source-registry-and-risk-gate
- 005-run-lifecycle-and-sweeper
- 006-rate-limiting-and-identification

**Deliverables**: `harvest-api` container joining the compose project and the release workflow;
`elestrals_harvest` schema with `price_sources`, `harvest_runs`; two MySQL users with
non-overlapping write grants; Celery worker + beat + Redis; `tos_review_note` and `risk_accepted_by`
both `NOT NULL` before `enabled = 1`, as a CHECK constraint; per-source token bucket; honest user
agent with contact address; outbound host allowlist.

**Assigned requirements**: FR-1, FR-13, and FR-2's run-recording criteria.

**Dependencies**: Depends on intent 001 unit 001 (platform auth, logging). Depended on by every
other unit here.
**Complexity**: M

---

### Unit 002: scrapers

**Description**: The two scan modes and the per-source connectors behind one contract. Deep asks the
whole catalog-derived query space; light re-checks known listings and looks for neighbours. Plus the
machinery that keeps an assertive scraper alive: recorded fixtures, drift detection, block detection
and quarantine.

**Stories**:
- 007-source-connector-contract
- 008-deep-scan
- 009-light-scan
- 010-connector-fixtures-and-drift-detection
- 011-block-detection-and-quarantine

**Deliverables**: `harvest/sources/` with registered connectors; `market_listings` migration; the
deep and light planners; recorded HTTP fixtures per connector; a drift test that **fails** when a
source's structure changes rather than silently returning nothing; quarantine state on
`price_sources` with automatic entry, backoff and a single probing retry.

**Assigned requirements**: FR-2, FR-18.

**Dependencies**: Depends on 001. Depended on by 003.
**Complexity**: L — **the highest-uncertainty unit in the intent.** It depends on third parties who
have not agreed to be depended on, and ADR-004 accepts that they may block us.

---

### Unit 003: matching-and-observations

**Description**: Resolve a listing title to a printing and a condition with a confidence, and record
it as an append-only observation with full provenance.

**Stories**:
- 012-title-to-printing-matcher
- 013-condition-extraction
- 014-observation-store-and-dedupe
- 015-sold-vs-listed-separation

**Deliverables**: `price_observations` migration; the matcher with a confidence floor that
**rejects** rather than guessing, and explicit refusals for graded slabs, lots, proxies and
unstocked languages; `UNIQUE (source_id, external_id)` dedupe; every row keeping its `source_url`;
the `sold`/`listed` split enforced against source configuration.

**Assigned requirements**: FR-3, FR-4.

**Dependencies**: Depends on 002, and on intent 001 unit 002 for the catalog it matches against.
Depended on by 004 and 005.
**Complexity**: L — the matcher is the accuracy ceiling for everything downstream.

---

### Unit 004: rollups-and-valuation

**Description**: Aggregate observations into daily statistics, publish them across the service
boundary, normalise currency, and value a collection or any slice of it — always with coverage and
confidence attached.

**Stories**:
- 016-daily-rollup-job
- 017-outlier-exclusion
- 018-fx-normalisation
- 019-price-daily-publication
- 020-collection-valuation
- 021-portfolio-history-and-pl
- 022-nightly-snapshot-valuation

**Deliverables**: `price_daily` + `fx_rates` migrations; IQR-based outlier exclusion; the
cross-schema read contract and the grant that limits it to exactly `price_daily`; the valuation
service that **excludes and counts** unpriced items rather than treating them as zero; back-filling
`collection_snapshots` with values from the day phase 1 started recording counts.

**Assigned requirements**: FR-5, FR-6, FR-8, FR-9.

**Dependencies**: Depends on 003, and on intent 001 unit 003 for inventory. Depended on by 006, 007.
**Complexity**: M

---

### Unit 005: admin-console

**Description**: Everything an admin does — authorise, look, judge, and run. The scope check, the
admin shell, the listing explorer, run history and health, on-demand scan control, and the analysis
that answers "is this data good enough to show anyone?"

**Stories**:
- 023-admin-scope-authorisation
- 024-admin-shell-and-routing
- 025-listing-explorer
- 026-run-history-and-health
- 027-trigger-and-watch-a-scan
- 028-coverage-and-match-quality
- 029-price-distribution-and-source-agreement

**Deliverables**: `elestrals:admin` gate as one shared dependency; `/admin/harvest/*` routes on
`harvest-api`; a code-split SPA admin section that a non-admin never downloads; the listing explorer
with confidence and rejection-reason filters; per-source health with accept-rate trend and
quarantine state; trigger/stop endpoints returning a run id immediately; coverage, match-quality,
price-distribution and source-agreement views.

**Assigned requirements**: FR-12, FR-14, FR-15, FR-16, FR-17.

**Dependencies**: 023–027 depend on 003 (there must be data to look at). 028–029 depend on 004.
**Complexity**: L — two surfaces (API and UI) across a service boundary, and the authorisation story
is the one that must not be got wrong.

> **This unit is deliberately scheduled before unit 004.** The raw data is admin-only precisely
> because scraped data has to be *judged* before anything is built on it. Building valuation first
> and the means to inspect it second would mean discovering the matcher is wrong through a user's
> portfolio number.

---

### Unit 006: price-surfaces

**Description**: Everything the collector sees — the card price tab, the market overview, the
portfolio, and the value columns that attach to the phase-1 collection table. Rollups only; no raw
listing ever reaches a non-admin.

**Stories**:
- 030-card-price-tab
- 031-market-overview
- 032-portfolio-page
- 033-slice-valuation

**Deliverables**: `/prices`, `/portfolio`, `/portfolio/slice`, the price tab on `/cards/:id`, value
and delta columns on `/collection`, `PriceSparkline` and `ConfidencePill`; the dashboard value tile
finally showing a number instead of "available in phase 2".

**Assigned requirements**: FR-7, FR-10.

**Dependencies**: Depends on 004.
**Complexity**: M

---

### Unit 007: alerts

**Description**: Price alerts for collectors, with a cooldown and an honest statement of what
triggered them.

**Stories**:
- 034-price-alerts

**Deliverables**: `price_alerts` migration; alert evaluation in the rollup job with cooldown;
delivery through the phase-1 outbox; alerts that never fire on `low` confidence data.

**Assigned requirements**: FR-11.

**Dependencies**: Depends on 004, and on intent 001 unit 007 for the outbox.
**Complexity**: S

---

## Unit Dependency Graph

```text
[001 harvest-service]
        └─> [002 scrapers]
                  └─> [003 matching-and-observations]
                            ├─> [005 admin-console 023-027]  ← the judgement gate
                            └─> [004 rollups-and-valuation]
                                      ├─> [005 admin-console 028-029]
                                      ├─> [006 price-surfaces]
                                      └─> [007 alerts]
```

The chain 001 → 002 → 003 is strictly sequential: there is no useful matching without listings, and
no listings without a service to hold them. After 003 the graph opens up, and the admin console's
first five stories should be taken before rollups — see the note on unit 005.

## Story counts

| Unit | Stories | Must | Should |
|---|---|---|---|
| 001 harvest-service | 6 | 6 | 0 |
| 002 scrapers | 5 | 5 | 0 |
| 003 matching-and-observations | 4 | 4 | 0 |
| 004 rollups-and-valuation | 7 | 7 | 0 |
| 005 admin-console | 7 | 7 | 0 |
| 006 price-surfaces | 4 | 3 | 1 |
| 007 alerts | 1 | 0 | 1 |
| **Total** | **34** | **32** | **2** |
