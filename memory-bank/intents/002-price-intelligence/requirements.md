---
intent: 002-price-intelligence
phase: inception
status: complete
created: '2026-08-09T12:00:00Z'
updated: '2026-08-17T23:55:00Z'
---

# Requirements: Price Intelligence

> **Amended 2026-08-15**, after the inception spike recorded in `adr-003-price-source.md` came
> back with "every direct route is closed, one licensed route is open at $49.99/mo". The human
> decision was: **do not pay, scrape instead**, run the harvester as a **second backend**, and
> keep the raw harvested data behind an **admin** claim. `adr-004-scrape-over-licence.md`
> records that decision, its consequences and its risk owner; ADR-003 is superseded.
>
> What changed here: FR-1 (the gate is now a *recorded risk*, not a veto), FR-2 (one daily job
> becomes two scan modes), FR-12 (folded into the admin console), and FR-13 to FR-18 are new.
> FR-4 is **restored to its original form** — see the note on it.

## Intent Overview

Every day, gather what Elestrals items **actually sold for** across the internet, normalise those
sales onto our printings and sealed products, and turn them into three things a collector can act
on: a defensible price history per item, a valuation of their collection or any slice of it, and
alerts when something crosses a threshold they care about.

The collection half runs as its own service — **`harvest-api`**, a second backend owning the
`elestrals_harvest` schema — so that a scraper being blocked, rate-limited or rewritten never
touches the availability of the collection tracker users are logged into.

The product promise is narrow and deliberate: **we report observed sales, we do not set prices.**
Every figure carries how it was derived and how confident it is.

**Who sees what.** The raw harvest — individual listings, run logs, match notes, rejected rows —
is visible only to holders of the `elestrals:admin` scope. Regular users see the aggregated
`price_daily` rollups through the phase-2 price surfaces, and never the listings underneath them.
That split is not only access control: the raw data is scraped, uneven and full of leads, and
showing it to a collector as though it were a product would misrepresent it.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Coverage | ≥ 80% of *owned* printings have a sold observation in the last 7 days | Must |
| Trust | 100% of displayed values carry an observation count, a window and a confidence level | Must |
| Freshness | The light scan completes within its window ≥ 95% of days; a deep scan completes weekly | Must |
| Usefulness | ≥ 50% of weekly-active users view `/portfolio` at least once a week | Should |
| Risk is recorded | 100% of enabled sources have a written terms review and a named risk owner | Must |
| Isolation | 0 user-facing incidents in the collection tracker caused by a harvester failure | Must |

> The legality goal from the original draft — *"100% of enabled sources have a recorded ToS
> review and a robots check"* — is replaced by **Risk is recorded**. The review still happens
> and is still mandatory, because you cannot accept a risk you have not read. What it no longer
> does is *block* enablement. See ADR-004 and NFR §Conduct.

---

## Functional Requirements

### FR-1: Source registry with a recorded-risk gate
- **Description**: Every source is a configured row carrying its access mode, rate limit,
  weighting, terms review, risk acceptance and kill switch. The review is recorded before the
  source can be enabled; it no longer has authority to refuse.
- **Acceptance Criteria**: A source cannot be set `enabled = 1` while `tos_review_note` is empty
  or while `risk_accepted_by` is null; both are enforced by a database constraint, not only by a
  service method; disabling a source takes effect on the next run with no deploy; the review note
  states what the terms actually say, so an accepted risk is an informed one.
- **Priority**: Must
- **Related Stories**: 002

### FR-2: Two scan modes, deep and light
- **Description**: Two scheduled jobs, separately triggerable, with retries, backoff and
  per-source rate limiting. **Deep** asks the whole catalog-derived query space and discovers
  items never seen before. **Light** re-checks known listings by id, closes the ones that have
  gone, and looks for new items near the products whose market just moved.
- **Acceptance Criteria**: Each run is recorded in `harvest_runs` *before* work starts; a source
  failing does not fail the run for other sources, and one query failing does not fail the run;
  the run ends `success | partial | failed`; a crashed run is swept to `failed` rather than
  remaining `running` forever; a deep run stays within 4 hours and a light run within 20 minutes.
- **Priority**: Must
- **Related Stories**: 003, 025

### FR-3: Match a sale to a printing
- **Description**: A matcher resolves a listing title to a `printing_id` (or
  `sealed_product_id`) plus a condition, recording a confidence.
- **Acceptance Criteria**: Matches below the confidence floor are rejected, not stored as
  low-confidence facts; graded slabs, multi-card lots and proxies are rejected outright with a
  stated reason; a language with no matching printing is rejected rather than folded onto the
  English one; `UNIQUE (source_id, external_id)` guarantees a re-run never double-counts; every
  observation retains its `source_url` so any figure is auditable back to origin; a rejected
  listing is still kept, with its reason, as a lead.
- **Priority**: Must
- **Related Stories**: 009, 010, 011

### FR-4: Sold versus listed
- **Description**: Observations are typed as `sold` or `listed` and are never mixed.
- **Acceptance Criteria**: Valuation uses `sold` only; a `listed` price may be shown as "asking",
  clearly labelled; a printing with only `listed` data is `low` confidence by definition; a
  source may only write `sold` rows when it genuinely reports completed sales, enforced against
  the source's configuration rather than the adapter's claim.
- **Priority**: Must
- **Related Stories**: 012

> **Restored, not amended.** ADR-003 was going to force this requirement to be weakened, because
> the licensed feed supplies aggregate market prices rather than a transaction log — no sale
> count, no sale window, no comparables. Scraping completed-listings pages gives back the actual
> sale price and the actual sale date, which is the one thing $49.99/mo could not buy. This is
> the strongest technical argument for the decision in ADR-004 and it belongs on the record next
> to the risk.

### FR-5: Daily rollups
- **Description**: A nightly job aggregates observations into `price_daily` (low, median, high,
  mean, counts, confidence) per printing, condition, day and currency.
- **Acceptance Criteria**: Charts and valuation read only `price_daily`, never the fact table;
  outliers beyond 3× the interquartile range are excluded from median and flagged; the rollup is
  rebuildable from observations; `price_daily` is the **only** harvest data readable by the
  collection backend, and it is exposed as a read-only view or a published table, never as a
  join into the harvester's private tables.
- **Priority**: Must
- **Related Stories**: 013, 014

### FR-6: Currency normalisation
- **Description**: Daily FX rates let a user see everything in their chosen currency.
- **Acceptance Criteria**: Conversion uses the rate for the observation's day, not today's; the
  original currency and amount remain visible on the sale record.
- **Priority**: Must
- **Related Stories**: 015

### FR-7: Price history on a card
- **Description**: The card detail page gains a price tab: history chart, per-condition and
  per-finish breakdown, contributing sources, and recent sales with links.
- **Acceptance Criteria**: Chart ranges 30/90/365 days and all-time; each series states its
  observation count; a printing with no data shows an honest empty state, not a flat line at
  zero; the tab reads rollups only and never exposes a raw listing row.
- **Priority**: Must
- **Related Stories**: 019

### FR-8: Collection valuation
- **Description**: Value a whole collection, or any filtered slice of it.
- **Acceptance Criteria**: Valuation is the sum over holdings of `quantity × median for that
  printing and condition`; items with no data are **excluded and counted separately**, never
  treated as zero; the result states coverage ("412 of 500 items valued") and an overall
  confidence; the same filters as `/collection` apply.
- **Priority**: Must
- **Related Stories**: 016, 022

### FR-9: Portfolio over time and P/L
- **Description**: Value history, cost basis versus market, and unrealized profit/loss.
- **Acceptance Criteria**: History is drawn from `collection_snapshots`, which phase 1 has been
  writing since launch; P/L is computed only over holdings that have a cost basis, and the
  covered proportion is stated; best and worst performers are listed.
- **Priority**: Must
- **Related Stories**: 017, 018, 021

### FR-10: Market overview
- **Description**: A public page of top movers, set indices and most-traded items.
- **Acceptance Criteria**: Movers require a minimum observation count to appear, so a single odd
  sale cannot top the list; indices are documented and reproducible.
- **Priority**: Should
- **Related Stories**: 020

### FR-11: Price alerts
- **Description**: A user sets a threshold on a printing, from the card page or a wishlist entry.
- **Acceptance Criteria**: Alerts fire at most once per cooldown window; delivery goes through
  notification-api via the phase-1 outbox; an alert states the price, the window and the
  confidence that triggered it; alerts never fire on `low` confidence data.
- **Priority**: Should
- **Related Stories**: 023

### FR-12: Harvest operations console
- **Description**: The admin-only view of per-source health. Folded into the admin dashboard
  (FR-15 to FR-17) rather than standing alone.
- **Acceptance Criteria**: Last run per mode, duration, fetched/parsed/accepted/rejected,
  accept-rate trend, terms-review state, risk owner and a kill switch per source; a sustained
  drop in accept rate raises an alert; a source that has started returning blocks is visibly
  distinguished from one that is merely finding nothing.
- **Priority**: Must
- **Related Stories**: 024

### FR-13: The harvester is a second backend
- **Description**: Collection runs as its own deployable service, `harvest-api`, owning the
  `elestrals_harvest` schema on the same MySQL instance. It reads the catalog cross-schema,
  read-only, and publishes `price_daily` for the collection backend to read.
- **Acceptance Criteria**: `harvest-api` has its own container, its own Alembic tree and its own
  schema; it holds **no write grant** on the `elestrals` schema, enforced by the database user's
  privileges rather than by convention; the collection backend holds no write grant on
  `elestrals_harvest`; `harvest-api` being down degrades price surfaces to their last rollup and
  never returns an error from a `/collection` request; both services are brought up by the same
  compose stack and the same release workflow.
- **Priority**: Must
- **Related Stories**: 026, 027

### FR-14: Admin authorisation
- **Description**: Every harvest surface — API and UI — requires the `elestrals:admin` scope on
  the caller's platform token.
- **Acceptance Criteria**: A caller without the scope receives `403` with no body detail, never a
  `200` with the interesting fields filtered out; the scope is read from the validated JWT and
  never from a request body, query parameter or header; the check lives in one dependency used by
  every admin route, so a new route cannot forget it; the admin section of the SPA is not
  rendered — not merely hidden — for a non-admin; a dev-only `sub` allowlist exists as the local
  escape hatch, matching the phase-1 operator pattern, and is inert in production.
- **Priority**: Must
- **Related Stories**: 028

### FR-15: Admin data explorer
- **Description**: Admins can see and filter everything the harvester holds — listings, their
  match notes, observations and runs.
- **Acceptance Criteria**: Filter by source, run, scan mode, status, matched/unmatched, kind and
  confidence band; every listing links to its `source_url` and shows why it matched or did not;
  unmatched listings are reachable in one click, because they are the queue of things the catalog
  or the matcher is missing; paging holds at 50k listings per source.
- **Priority**: Must
- **Related Stories**: 029

### FR-16: Admin analysis
- **Description**: The tools for deciding whether the harvested data is good enough to show
  anyone — coverage, match quality, price distributions and source agreement.
- **Acceptance Criteria**: Coverage of tracked printings over time; accept-rate trend per source
  and per scan mode; the top rejection reasons, grouped and counted, so the biggest matcher gap
  is visible without reading rows; price distribution per printing with the outliers the rollup
  excluded marked; where two sources both cover a printing, their disagreement is quantified.
- **Priority**: Must
- **Related Stories**: 030, 031

### FR-17: Run the scrapers from the dashboard
- **Description**: An admin can start either scan on demand and watch it, without a shell.
- **Acceptance Criteria**: Deep and light are separately triggerable per source; the trigger
  returns immediately with a run id rather than blocking; a run in progress is visible with live
  counters; a second run of the same source and mode is refused while one is running, rather than
  queued invisibly; a running scan can be stopped, and stopping ends the run `partial` with what
  it had; the on-demand path and the scheduled path are the same code.
- **Priority**: Must
- **Related Stories**: 032, 033

### FR-18: Survive being blocked
- **Description**: Assertive collection means blocks are an operating condition, not an
  incident. The system detects them, backs off, and says so.
- **Acceptance Criteria**: A source returning a sustained pattern of 403/429/challenge responses
  is automatically quarantined rather than retried into a harder block; a quarantined source is
  visibly distinguished in the console from one that is simply finding nothing; quarantine
  expires on a configured backoff and the source is retried once before being quarantined again;
  a block never fails the other sources' runs; the last-known-good rollups continue to serve
  every user surface while a source is quarantined.
- **Priority**: Must
- **Related Stories**: 034

---

## Non-Functional Requirements

### Performance
| Requirement | Metric | Target |
|---|---|---|
| Price history load | p95 | < 250ms (reads `price_daily` only) |
| Collection valuation, 5k holdings | p95 | < 1.5s |
| Admin listing explorer, 50k rows | p95 | < 400ms per page |
| Deep scan | wall clock | < 4 hours |
| Light scan | wall clock | < 20 minutes |
| Rollup job | wall clock | < 20 minutes |

### Scalability
| Requirement | Metric | Target (12-month) |
|---|---|---|
| `price_observations` | rows | 50M |
| `price_daily` | rows | 20M |
| `market_listings` | rows | 2M |
| Tracked printings | rows | 50,000 |

### Security & Authorisation
| Requirement | Standard | Notes |
|---|---|---|
| Admin gate | `elestrals:admin` scope on the platform token | one dependency, every admin route; `403`, never a filtered `200` |
| Service isolation | database grants | `harvest-api` has no write grant on `elestrals`; the collection backend has none on `elestrals_harvest` |
| Outbound | allowlisted hosts only | the harvester cannot be steered to arbitrary URLs, including via a redirect |
| Data | no personal data collected from sources | prices, dates, titles and URLs only — never buyer or seller identity |
| Egress | no user data leaves | the harvester reads outward and writes inward, nothing else |
| Secrets | no source credentials in the SPA | the admin UI triggers runs through `harvest-api`; it never holds a source credential |

### Conduct
| Requirement | Standard | Notes |
|---|---|---|
| Identification | honest user agent + contact address | **kept.** We remain identifiable to every site we read, so a site can ask us to slow down instead of having to block us |
| Rate | per-source limit, configurable | **raised.** Rates are set per source for throughput rather than for minimum footprint |
| robots.txt | **not obeyed** | Decided 2026-08-15 (ADR-004). Recorded here rather than left implicit: this is a deliberate choice, it is the choice most likely to attract a block, and it is the one an outside reader will ask about first |
| Terms of service | reviewed and knowingly accepted | TCGplayer and eBay both prohibit scraping. The review is written down and a named person accepts the risk per source; it does not veto enablement |
| Personal data | none collected | unchanged, and worth restating: the conduct posture moved on politeness, not on privacy |

### Reliability
| Requirement | Metric | Target |
|---|---|---|
| Light scan success | rolling 30-day | ≥ 95% |
| Source isolation | one source failing or blocked | never fails another source's run |
| Service isolation | `harvest-api` down | price surfaces serve last-known rollups; `/collection` unaffected |
| Rebuildability | rollups | fully regenerable from observations |

### Compliance
| Requirement | Standard | Notes |
|---|---|---|
| Source terms | per-source review, recorded, re-reviewed annually | accepted risk with a named owner — see ADR-004 |
| Financial framing | not investment advice | a visible disclaimer; we report observed sales, we do not advise |
| Data provenance | every figure traceable to a URL | unchanged, and load-bearing: it is what makes "we report observed sales" checkable |

---

## Constraints

### Technical Constraints

**Project-wide standards**: loaded from `memory-bank/standards/` by the Construction Agent.

**Intent-specific:**
- **Two backends, one MySQL instance, two schemas.** `harvest-api` owns `elestrals_harvest`;
  `elestrals` stays owned by the collection backend. Cross-schema reads are read-only and
  one-directional in each case. Separate Alembic trees; neither service migrates the other's
  schema.
- Jobs move from in-process APScheduler to **Celery + Redis**, inside `harvest-api`. Retries,
  isolation and queueing per source class are requirements here, not conveniences.
- `price_observations` is append-only. Corrections are new rows plus exclusion, never edits — a
  price history that can be silently rewritten is not evidence.
- No figure renders without its confidence. The `ConfidencePill` is a required prop on the money
  component, not an optional one.
- The admin SPA section is code-split and gated on the scope, so a non-admin never downloads it.

### Business Constraints
- **No recurring data cost.** The $49.99/mo licensed feed is declined; collection is by scraping.
  This is the constraint that produced ADR-004 and FR-18.
- The risk accepted in ADR-004 is revisited if a source sends a cease-and-desist, changes its
  terms materially, or if the project ever charges users — the last one changes the character of
  the risk, not just its size.

---

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|---|---|---|
| Scraped completed-listings pages carry a real sale price and date | FR-4 collapses again and valuation loses its `sold` basis | Verified per source during unit 002 before that source is enabled; a source that cannot supply it is configured to write `listed` only |
| Sources can be scraped at a useful rate before blocking | Coverage collapses; the intent degrades to whatever survives | FR-18: quarantine, backoff, and a console that shows a block as a block. Rates are per-source and tunable without a deploy |
| Listing titles carry enough signal to identify a printing | Matcher rejects most rows | Confidence floor with rejection rather than guessing; per-source title rules; manual mapping for high-value printings |
| Sold volume is high enough for a meaningful median | Most printings sit at `low` confidence | Honest confidence display — a sparse market shown truthfully still beats a fabricated number |
| Phase 1 has been writing `collection_snapshots` since launch | Portfolio history starts empty on the day phase 2 ships | Already handled: the snapshot table was built in phase 1 for this reason |
| The platform can issue an `elestrals:admin` scope | FR-14 falls back to the dev `sub` allowlist in production, which is not an authorisation system | Confirm with the platform before unit 006; the operator pattern in phase 1 has the same dependency and the same provisional note |

---

## Open Questions

| Question | Owner | Due | Resolution |
|---|---|---|---|
| Which sources have an official API for sold data, and on what terms? | Lars | before unit 002 | **Resolved 2026-08-12** (ADR-003): none obtainable. Superseded by ADR-004 — collection is by scraping |
| Do we need a licensed data agreement to display aggregated prices commercially? | Lars | before phase 3 | **Pending**, and now sharper: ADR-004's accepted risk changes character the moment the marketplace charges a fee |
| Can the platform issue an `elestrals:admin` scope, or must we allowlist subs? | Lars | before unit 006 | **Pending** |
| Median, or trimmed mean, as the headline figure? | Lars | during unit 004 | Leaning median with IQR outlier exclusion — resistant to the single silly sale, and explainable to a user |
| At what point does a block become a stop, rather than a backoff? | Lars | before first enablement | **Pending** — FR-18 automates the backoff; the decision to stop reading a source entirely is a human one |
