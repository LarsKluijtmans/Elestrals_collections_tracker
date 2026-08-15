---
adr: 001
title: Catalog source of truth — curated seed, not a scraped source
status: accepted
date: 2026-08-10
bolt: 002-card-catalog-schema-import
stage: 0-spike
---

# ADR-001: Catalog source of truth

## Context

Bolt 002 stage 0 is a timeboxed spike with one question:

> Does a public source carry Elestrals card data at printing-level fidelity — rarity, finish,
> language, edition — under terms we can live with?

The answer determines whether `008-catalog-importer` is a network adapter over a live source or a
loader over a hand-maintained seed. The bolt was scheduled second precisely so this surfaces while
the schema is still cheap to change.

### What the spike found

**A first-party product already occupies this space.** `collect.elestrals.com` — "Collect!
Elestrals: The Official Elestrals Collection Tracker", operated by Elestrals LLC — offers
collection tracking, browse-by-set, missing-card views and a serialized-Stellar registry. This was
not known at inception and is not in `project/project-brief.md`.

**The data is real and well-structured.** Set pages are server-rendered and carry usable content:

| Source | What it yields | Fidelity |
|---|---|---|
| `collect.elestrals.com/sets` | ~30 sets with codes — FE01–FE04, DC00–DC04, OP-1–OP05, SS01–SS04, KS00–KS03, EP00/EP01, CON1 | set-level: good |
| `collect.elestrals.com/sets/FE01` | 126 cards: collector number (`BS1-001`), name, image | card-level: good |
| same page, filter facets | `Normal` / `Holo` canvas types; "13 Serialized Stellars" | printing-level: **partial** — variants exist as filters, not as per-card labels |
| `the-elestrals-archives.fandom.com` | community wiki, CC-BY-SA text | unverified — blocked our fetch (HTTP 402) |
| `tcgautomate.com/card-checklists/elestrals` | set abbreviations and counts | unverified — blocked our fetch (HTTP 403) |
| TCGplayer | price guide category | inconclusive from public pages; has its own partner API and terms |

No public REST API was found (`/api/cards` → 404), and no `robots.txt` exists on the collect
subdomain at all. No open GitHub dataset for Elestrals was located.

**The terms are the blocker, not the fidelity.** `elestrals.com/terms` (redirects to
`elestrals-next.cereal.app/terms`) prohibits, verbatim:

- *"use software or automated agents or scripts … to strip, scrape, or mine data from the Site"*
- *"you shall not access the Site in order to build a similar or competitive website, product, or service"*
- *"no part of the Site may be copied, reproduced, distributed, republished, downloaded, displayed, posted or transmitted in any form or by any means"*
- *"all the intellectual property rights … in the Site and its content are owned by Company or Company's suppliers"*

Users hold only a *"non-transferable, non-exclusive, revocable, limited license"* for personal,
noncommercial use. The one carve-out for automated access covers search-engine spiders building
searchable indices, subject to `robots.txt` — which does not apply to us.

All three clauses land on this project simultaneously: it is a collection tracker (competitive
product), the importer would be an automated agent (scraping), and the catalog would be a
reproduction of their content. This is not a rate-limit-and-be-polite situation that a good user
agent and a crawl delay can resolve.

## Decision

**Fall back to the curated CSV seed**, exactly as the bolt's decision rule prescribes for a "No".

The canonical model does not change. `sets` / `cards` / `printings` / `sealed_products` /
`catalog_imports` stay as specified in `standards/data-model.md`, and the idempotent upsert stays
as specified. Only the source of truth changes:

- Source adapters remain the extension point — the interface is unchanged, so a licensed or
  permitted source can be added later as one adapter file plus one config row.
- Phase 1 ships with a `CsvSeedAdapter` reading version-controlled per-set CSVs under
  `backend/data/catalog/{SET}.csv`, hand-compiled from physical cards and publicly published
  checklists.
- Card **facts** — set code, collector number, name, rarity, finish — are compiled independently.
  Card **images and card text are not redistributed**; the brief's existing rule (link or
  thumbnail with attribution, written permission before phase 3) continues to govern.

## Alternatives considered

1. **Scrape `collect.elestrals.com` with polite rate limits.** Rejected — the prohibition is on
   access-for-competing-product and on scraping as such, not on request volume. Politeness does not
   cure it.
2. **Fandom wiki (CC-BY-SA) as the adapter source.** Deferred, not dismissed. The licence is
   plausibly compatible for compiled text, but the fetch was blocked so fidelity is unverified, and
   the underlying card designs remain publisher IP. Worth a follow-up spike if seed maintenance
   becomes the bottleneck.
3. **TCGplayer partner API.** Deferred to phase 2, where it is the natural price source anyway.
   Its terms need their own review; it does not solve phase 1's catalog need on its own.
4. **Request written permission from Elestrals LLC.** Recommended in parallel — it is the only
   route that makes a live official source available, and it costs one email. It does not block
   phase 1.

## Consequences

**Good**

- Phase 1 proceeds on schedule with no legal exposure from the catalog.
- The decision lands in week one, before the inventory UI is built on the assumption, which is the
  entire point of scheduling the spike here.
- The seed is deterministic and offline, so importer tests need no network and no fixtures scraped
  from a third party. Success criteria "second run over unchanged sources: 0 added, 0 updated" and
  "full re-import < 15 minutes" become trivially satisfiable.

**Bad**

- Catalog freshness is now a manual commitment. A new set means someone compiles a CSV. The brief's
  "catalog drift" risk gets sharper, and the catalog-health dashboard matters more, not less.
- Coverage at launch is bounded by how many sets are hand-compiled. Starting with FE01 (126 cards)
  satisfies the bolt's "one real set, complete and correct" criterion.

**Strategic — outside this bolt's scope, flagged for the human**

An official, free, first-party tracker already exists. That is a product-positioning question, not
an architecture one, and it should be answered before phase 3 commercial work. It also raises the
trademark/affiliation risk already listed in `project/project-brief.md` from theoretical to live.

## Follow-ups

- [ ] Human decision: continue given the official tracker exists, and on what differentiator
- [ ] Send a permission request to Elestrals LLC for catalog data use (unblocks alternative 1)
- [ ] Add a "competing first-party product" row to `project/project-brief.md` Key Risks
- [ ] Re-spike the Fandom wiki route if seed maintenance becomes the bottleneck
