---
created: 2026-08-09T12:00:00Z
updated: 2026-08-09T12:00:00Z
---

# Project Brief

## Project Name

**Elestrals Collection Tracker** (working product name: **Elestral Vault**)

## Overview

A web application where Elestrals TCG collectors track what they own — singles, sealed packs,
boosters and boxes — see what their collection is worth from real observed market prices, and
eventually buy and sell with each other on the site itself.

It is built as a **client application of the in-house auth platform** (`../auth`). Authentication,
branding, notifications, logging and usage metering are all consumed from that platform rather than
rebuilt here. The application owns one thing the platform does not: the **Elestrals domain** — the
card catalog, user inventory, observed prices and the marketplace.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Collectors can catalog their whole collection without friction | A user can enter 100 cards in < 10 minutes; median add-a-card interaction < 5s | Must |
| Collectors trust the valuation | ≥ 80% of owned printings have a price observed in the last 7 days | Must |
| Collectors return regularly | ≥ 35% week-4 retention of users who added ≥ 20 cards | Should |
| Collectors transact on-site | ≥ 100 active listings within 60 days of marketplace launch | Could (phase 3) |

## Target Users

1. **The completionist** — wants set-completion percentages, a missing-cards list, and a wishlist.
2. **The investor** — wants portfolio value over time, cost basis, and unrealized profit/loss.
3. **The trader** — wants to know a fair price *before* buying or selling, and eventually to
   transact on-site.
4. **The operator (us)** — needs catalog imports, scraper health and abuse tooling.

## Scope by Phase

| Phase | Intent | Delivers |
|-------|--------|----------|
| 1 | `001-collection-tracker` | Card catalog, inventory of singles + sealed, sets/completion, wishlist, CSV import/export |
| 2 | `002-price-intelligence` | Daily price scraping of sold items, price history, valuation of a collection or any slice of it, alerts |
| 3 | `003-marketplace` | On-site listings, discovery, messaging, orders, reputation |

Each phase is independently shippable and independently valuable. Phase 2 is worthless without
phase 1's catalog; phase 3 is worthless without phase 2's price guidance.

## Success Criteria

- [ ] A signed-in user can add, edit and remove inventory across all card variants and conditions
- [ ] Set completion is computed correctly for every released set
- [ ] A nightly job produces price observations for the tracked printings, with per-source health visible
- [ ] Collection value, and the value of any filtered slice, is computed from those observations with a stated confidence
- [ ] Every app event is written to our own `app_logs` table, with errors and security events forwarded to the platform's logs-api
- [ ] Feature usage is metered to the platform (`usage.track`) so the console reports real product usage

## Non-Goals

- Building a deck builder or a rules engine — this is a collection and market product, not a play aid
- Re-implementing authentication, branding, notification or logging infrastructure
- Becoming a grading service or a price *oracle* — we report observed sales, we do not set prices

## Key Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Trademark / affiliation.** "Elestrals" is a trademark of the game's publisher. | Takedown, forced rename, blocked marketplace | Ship a clear "unofficial, not affiliated with or endorsed by the publisher" notice; keep the product name distinct from the trademark; do not host card art we do not have rights to — link or thumbnail with attribution, and get written permission before phase 3 |
| **Price-source terms of service.** Scraping marketplaces may violate their ToS. | Loss of the entire phase-2 data supply | Prefer official APIs where they exist; per-source `robots.txt` + ToS review recorded in `price_sources`; conservative rate limits; a source can be disabled without code change |
| **Catalog drift.** New sets and reprints land continuously. | Users cannot record new cards; completion is wrong | Importer is idempotent and re-runnable per set; catalog health dashboard shows staleness |
| **Marketplace liability** (phase 3) | Legal and financial exposure | Commercial model deliberately deferred — see `intents/003-marketplace/requirements.md`; phase-1 data model stays payment-agnostic so either route stays open |

## Timeline (indicative, not committed)

- **Inception**: 2026-08-09
- **Phase 1 construction**: 7 bolts — see `memory-bank/bolts/`
- **Phase 2 construction**: begins after phase 1 has real inventory data to value
- **Phase 3**: commercial model decided first, then planned
