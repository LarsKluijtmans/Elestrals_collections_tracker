---
adr: 003
title: Price source — a licensed aggregator, because every direct route is closed
status: proposed
date: 2026-08-12
intent: 002-price-intelligence
stage: inception-spike
---

# ADR-003: Where phase 2's prices come from

**Status is `proposed`, not `accepted`: this one costs money, and that is the human's call.**

## Context

`intent 002 → requirements.md` FR-1 makes the gate explicit before any code exists: every enabled
source needs a recorded ToS review and a robots check, and *"prefer an official API over scraping
wherever one exists."* The Must-level business goal is **100% of enabled sources** cleared that way.

ADR-001 already showed what happens when that gate is applied honestly — the catalog's obvious
source turned out to be prohibited, and phase 1 fell back to a hand-compiled seed. The same
question decides whether phase 2 is buildable at all, so it was asked before planning any bolts.

## What the spike found

**Both official routes are closed to us.**

| Route | State |
|---|---|
| **TCGplayer API** | Public applications closed since late 2024 (eBay-owned since 2022). Access is limited to existing key holders, large sellers and approved partners; applying today "expects silence rather than a key" |
| **eBay Marketplace Insights** (sold history) | A **Limited Release** API. eBay's own documentation: *"restricted and not open to new users at this time."* Approval is for enterprise partners |
| **eBay Browse API** | Open, but returns **active listings only** — not the sold data FR-4 is built around |
| **Scraping either** | Prohibited by both sets of terms. This is the ADR-001 situation again, and the answer does not change because we want it more |

**One obtainable source carries Elestrals.**

[TCG API](https://tcgapi.dev/games/elestrals) — verified on its dedicated Elestrals page, not
inferred from a marketing summary:

| | |
|---|---|
| Coverage | **2,682 cards · 50 sets** |
| Print types | 2 — Normal and Foil |
| Refresh | **every 3 days** (not daily; Elestrals is in the "All Games" tier, not the 9 daily ones) |
| History | weekly data points from March 2025, **Pro tier and above only** |
| Provenance | *"All coverage sourced through TCGPlayer listings"* |
| Commercial licence | **Pro $49.99/mo** or Business $99.99/mo. Free/Hobby/Starter are explicitly non-commercial |

A second aggregator, JustTCG, was checked and **does not cover Elestrals** (18 games, Elestrals
absent).

## Decision (proposed)

**License TCG API at the Pro tier and treat it as the single phase-2 source**, behind the same
`SourceAdapter`-shaped port the catalog importer already uses. No scraping in phase 2.

## What this forces us to change in the requirements

This source is real but it is *not* the source FR-2 to FR-4 were written against. Three of them
need amending before construction, and pretending otherwise would build features on a feed that
cannot supply them:

1. **FR-2 "Daily collection of sold prices" → every 3 days.** The Elestrals tier refreshes on a
   3-day cadence. A nightly job would re-read unchanged numbers and report false freshness.
2. **FR-4 "Sold versus listed" is no longer a distinction we can make ourselves.** We receive
   market / low / foil prices derived from TCGplayer listings, not a raw transaction feed.
   TCGplayer's market price *is* sale-derived, so the number is meaningful — but we cannot show a
   sale count, a sale window, or individual comparables. `ux-guide.md` §12 says the valuation
   number must always show what it is built from; with this source, honestly, that is
   *"aggregator market price, refreshed every 3 days"* and nothing finer.
3. **FR-3 "Match a sale to a printing" gets lossy.** They model 2 print types; our `printings`
   table is rarity × finish × language × edition. A single upstream row may map to several of our
   printings, and the mapping needs an explicit confidence rather than a silent best guess.

The `price_observations` / `price_daily` split in `standards/data-model.md` survives unchanged —
it just gets one source row rather than several scrapers.

## Consequences

**Good**

- Phase 2 becomes legal and buildable, with a licence rather than a ToS gamble.
- No scraper fleet: no robots.txt machinery, no rate limiting, no per-source health, no
  `scrape_runs` in phase 1's sense. The unit brief's biggest operational burden disappears.
- FR-1's Must ("100% of enabled sources have a recorded ToS review") is satisfiable, because
  there is exactly one source and this document is its review.

**Bad**

- **A recurring cost, ~$600/year**, for a project with no revenue. That is the decision.
- Single point of dependency. If they drop Elestrals or change terms, phase 2 stops. The adapter
  port keeps the swap cheap, but there is no second source to swap to today.
- Coarser than designed: 3-day refresh, weekly history, no comparables.
- History only reaches back to March 2025.

## The part that also affects phase 1

**This may reopen ADR-001.** The same licence covers **2,682 Elestrals cards across 50 sets** —
which is precisely the catalog data `FE01.csv` is empty for. ADR-001 fell back to a hand-compiled
seed because the *publisher's* terms prohibited scraping their site; it did not consider a
licensed third party, because none was known to carry Elestrals.

Before anyone hand-compiles 126 cards, confirm with TCG API whether the Pro licence covers
displaying **catalog** fields (names, numbers, rarities, set structure) and not only prices. If it
does, one subscription closes phase 1's last open criterion and supplies phase 2. If it does not,
the seed stands and only prices come from here.

That question is worth one email before any data entry.

## Follow-ups

- [ ] **Human decision: pay $49.99/mo?** Everything below waits on it
- [ ] Confirm the licence covers catalog fields, not just prices — decides whether ADR-001 reopens
- [ ] Read the full terms properly; this spike read the pricing and coverage pages, not the ToS
- [ ] Amend FR-2, FR-3 and FR-4 in `requirements.md` to match a 3-day aggregate feed
- [ ] Re-check TCGplayer API access annually — an approved key would supersede this
