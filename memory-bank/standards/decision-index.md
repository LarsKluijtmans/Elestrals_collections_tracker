---
last_updated: 2026-08-10T12:55:00Z
total_decisions: 1
---

# Decision Index

This index tracks all Architecture Decision Records (ADRs) created during Construction bolts.
Use this to find relevant prior decisions when working on related features.

## How to Use

**For Agents**: Scan the "Read when" fields below to identify decisions relevant to your current task. Before implementing new features, check if existing ADRs constrain or guide your approach. Load the full ADR for matching entries.

**For Humans**: Browse decisions chronologically or search for keywords. Each entry links to the full ADR with complete context, alternatives considered, and consequences.

---

## Decisions

### ADR-001: Catalog source of truth — curated seed, not a scraped source
- **Status**: accepted
- **Date**: 2026-08-10
- **Bolt**: 002-card-catalog-schema-import (002-card-catalog)
- **Path**: `bolts/002-card-catalog-schema-import/adr-001-catalog-data-source.md`
- **Summary**: The bolt-002 spike asked whether a public source carries Elestrals card data at printing-level fidelity under acceptable terms; the data exists and is well-structured, but the publisher's Terms of Use explicitly prohibit scraping, accessing the site to build a competing product, and reproducing site content. Phase 1 ships a curated per-set CSV seed behind the unchanged adapter interface, leaving the canonical model and idempotent upsert exactly as designed.
- **Read when**: catalog import, card data sourcing, source adapters, scraping, `robots.txt`, terms of service, licensing, catalog freshness or drift, adding a new data source, or any question about where `sets`/`cards`/`printings` rows come from.
