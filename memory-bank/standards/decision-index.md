---
last_updated: 2026-08-15T14:40:00Z
total_decisions: 4
---

# Decision Index

This index tracks all Architecture Decision Records (ADRs) created during Construction bolts.
Use this to find relevant prior decisions when working on related features.

## How to Use

**For Agents**: Scan the "Read when" fields below to identify decisions relevant to your current task. Before implementing new features, check if existing ADRs constrain or guide your approach. Load the full ADR for matching entries.

**For Humans**: Browse decisions chronologically or search for keywords. Each entry links to the full ADR with complete context, alternatives considered, and consequences.

---

## Decisions

### ADR-004: Scrape rather than licence — the cost is declined and the risk is accepted
- **Status**: **accepted** — the human decision ADR-003 was waiting for
- **Date**: 2026-08-15
- **Intent**: 002-price-intelligence (inception)
- **Path**: `intents/002-price-intelligence/adr-004-scrape-over-licence.md`
- **Risk owner**: Lars Kluijtmans
- **Summary**: The $49.99/mo licensed aggregator proposed in ADR-003 is declined. Collection is by
  scraping, robots.txt is deliberately not obeyed, request rates are set for throughput, and the
  user agent stays honest and identifiable. TCGplayer's and eBay's terms prohibit this; the terms
  review is still mandatory before enablement but records an accepted risk rather than issuing a
  veto (`risk_accepted_by NOT NULL` before `enabled = 1`). The technical case: scraped
  completed-listings pages carry a real sale price and date, so FR-4's sold/listed distinction
  survives intact where the aggregate feed would have forced FR-2, FR-3 and FR-4 to be weakened.
  The costs accepted are contractual exposure, blocks as a normal operating condition (FR-18), and
  connector maintenance in place of a subscription. Structurally isolated in a second backend
  (FR-13) so a blocked scraper cannot degrade the collection tracker.
- **Read when**: price sources, scraping, robots.txt, terms of service, risk acceptance,
  `price_sources`, blocks and quarantine, the second backend's existence, why phase 2 has no
  subscription — and **before** enabling any source for the first time.

### ADR-003: Price source — a licensed aggregator, because every direct route is closed
- **Status**: **superseded** by ADR-004 — the research stands, the conclusion does not
- **Date**: 2026-08-12
- **Intent**: 002-price-intelligence (inception spike, before bolt planning)
- **Path**: `intents/002-price-intelligence/adr-003-price-source.md`
- **Summary**: FR-1 requires every price source to clear a ToS review and to prefer an official API, but TCGplayer's API has been closed to new applicants since late 2024 and eBay's Marketplace Insights is a restricted Limited Release, leaving scraping — which both sets of terms prohibit. One obtainable aggregator (TCG API) carries Elestrals at 2,682 cards across 50 sets with a commercial licence at $49.99/mo, refreshing every 3 days rather than daily, so FR-2, FR-3 and FR-4 need amending before construction. The same licence may also cover the catalog data phase 1's empty FE01 seed needs, which would reopen ADR-001.
- **Read when**: you need the *map* of what price routes exist and on what terms — TCGplayer's closed API, eBay's Limited Release sold-history, Browse's active-listings-only limitation, the aggregator's coverage and price. For the decision taken on that map, read ADR-004 instead.

### ADR-002: Card search — tiered SQL scan, not FULLTEXT
- **Status**: accepted
- **Date**: 2026-08-10
- **Bolt**: 003-card-catalog-surface (002-card-catalog)
- **Path**: `bolts/003-card-catalog-surface/adr-002-search-implementation.md`
- **Summary**: Story 010 needs ranked search under 150ms p95 with an explicit, totally-ordered tier ranking that bolt 005's keyboard add-flow can safely commit against; at ~5,000 cards a direct query with a `CASE` tier expression sits two orders of magnitude inside the budget. FULLTEXT was rejected because its default minimum token size of 3 silently breaks two-character searches and its relevance score competes with the required tier order, and a token table was deferred because it buys performance we do not need at the price of a projection that can go stale.
- **Read when**: card search, ranking, relevance, `MatchKind`, search performance, FULLTEXT, autocomplete, the fast-add keyboard flow, or any question about why search is a plain query rather than an index.

### ADR-001: Catalog source of truth — curated seed, not a scraped source
- **Status**: accepted
- **Date**: 2026-08-10
- **Bolt**: 002-card-catalog-schema-import (002-card-catalog)
- **Path**: `bolts/002-card-catalog-schema-import/adr-001-catalog-data-source.md`
- **Summary**: The bolt-002 spike asked whether a public source carries Elestrals card data at printing-level fidelity under acceptable terms; the data exists and is well-structured, but the publisher's Terms of Use explicitly prohibit scraping, accessing the site to build a competing product, and reproducing site content. Phase 1 ships a curated per-set CSV seed behind the unchanged adapter interface, leaving the canonical model and idempotent upsert exactly as designed.
- **Read when**: catalog import, card data sourcing, source adapters, scraping, `robots.txt`, terms of service, licensing, catalog freshness or drift, adding a new data source, or any question about where `sets`/`cards`/`printings` rows come from.
