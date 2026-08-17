---
adr: 004
title: Scrape rather than licence — the cost is declined and the risk is accepted
status: accepted
date: 2026-08-15
intent: 002-price-intelligence
stage: inception
supersedes: adr-003-price-source
risk_owner: Lars Kluijtmans
---

# ADR-004: Collection is by scraping, and the risk that comes with it

**Status is `accepted`.** ADR-003 was `proposed` because it cost money and that was not the
agent's call. It was put to the human on 2026-08-15 and the answer was: **do not pay, scrape it
all.** This record exists so that answer is on the record with its consequences attached, rather
than surviving only as a sentence in a chat log.

## Context

`adr-003-price-source.md` asked whether phase 2 was buildable at all, and found:

| Route | State |
|---|---|
| TCGplayer API | closed to new applicants since late 2024 |
| eBay Marketplace Insights (sold history) | Limited Release, "restricted and not open to new users" |
| eBay Browse | open, but **active listings only** — asking prices, not sales |
| TCG API (licensed aggregator) | obtainable, $49.99/mo, 3-day refresh, aggregate prices |
| Scraping any of them | prohibited by their terms |

ADR-003 proposed the licensed aggregator. Its own "Bad" column listed the price: ~$600/year on a
project with no revenue, a single point of dependency, a 3-day refresh instead of daily, and — the
one that mattered most — **no transaction feed**, which would have forced FR-2, FR-3 and FR-4 to be
weakened before construction.

## Decision

**Collect by scraping. Do not licence. Do not obey robots.txt. Remain identified.**

Concretely:

1. Sources are scraped, including sources whose terms prohibit it.
2. `robots.txt` is **not** consulted as a permission gate (NFR §Conduct).
3. Request rates are set per source for throughput, not for minimum footprint.
4. The user agent stays honest: product name, version, and a contact address.
5. Every source still gets a **written terms review** before it can be enabled, and a **named
   person accepts the risk** — `price_sources.risk_accepted_by`, `NOT NULL` before `enabled = 1`.
6. No personal data is collected from any source. Prices, dates, titles and URLs only.

## What this buys

**FR-4 survives intact, and that is the technical case for this decision.** The licensed feed
supplies aggregate market prices derived from listings — no sale count, no sale window, no
comparables. Scraped completed-listings pages carry the actual sale price and the actual sale
date. Valuation built on `sold` observations was the original design and it is only reachable
this way. ADR-003 was going to cost $600/year *and* deliver the weaker product.

Also: daily rather than 3-day freshness, more than one source, and no vendor who can drop
Elestrals coverage and end phase 2 with an email.

## What this costs

**The terms.** TCGplayer's and eBay's terms prohibit scraping. This decision knowingly acts
against them. That is a contractual exposure, not a technical one, and no amount of engineering
removes it — the mitigations below reduce the chance of *noticing* and the damage when noticed,
not the fact.

**Not obeying robots.txt.** This is the choice most likely to attract a block, and the first thing
an outside reader will ask about. It is recorded in NFR §Conduct rather than left implicit,
because a convention broken silently reads as a convention nobody knew about.

**Blocks become an operating condition.** Hence FR-18: sustained 403/429/challenge responses
quarantine a source automatically rather than retrying into a harder block. A pipeline built on
assertive scraping that has no quarantine story will spend its first outage making things worse.

**Fragility.** Scrapers break when a site changes its markup, and they break silently — returning
zero rows looks identical to a quiet market. Hence recorded HTTP fixtures and a drift test per
connector (story 010), and the accept-rate trend in the admin console (story 028).

**Ongoing effort replaces ongoing cost.** $600/year is declined; the maintenance of N connectors
is accepted in its place. This is a real trade, not a saving.

## Consequences for the requirements

Unlike ADR-003, this decision **does not force any requirement to be weakened**. FR-2, FR-3 and
FR-4 stand as originally written. What it adds:

- **FR-1** changes from a legal *veto* to a recorded *risk acceptance*. The review still happens
  and still blocks enablement when missing — you cannot accept a risk you have not read — but a
  prohibitive answer no longer stops the source.
- **FR-18** is new and exists only because of this decision.
- The business goal "Legality" becomes "Risk is recorded".

## Consequences for the architecture

Scraping at an assertive rate is a noisy, blockable, failure-prone activity, and it now lives in
the same process as the app users are logged into. It should not. Combined with the decision to
run the harvester as a second backend (FR-13), the isolation is structural:

- `harvest-api` owns `elestrals_harvest`; it holds **no write grant** on `elestrals`.
- The collection backend reads `price_daily` and nothing else of the harvester's.
- A blocked, crashed or rewritten scraper cannot degrade `/collection`.

The second backend was asked for independently, but this decision is what makes it load-bearing
rather than tidy.

## Review triggers

This decision is revisited — not automatically reversed — when any of these happens:

| Trigger | Why it changes the calculation |
|---|---|
| A cease-and-desist, or any direct contact from a source | The risk stops being theoretical |
| A source materially changes its terms | The accepted risk is no longer the one that was accepted |
| **The project charges users anything** | Commercial use of scraped data is a different exposure from a hobby project's, in kind and not only in degree |
| TCGplayer reopens API applications | An approved key supersedes this entirely — re-check annually |
| Sustained quarantine of a majority of sources | The approach has stopped working on its own terms |

## Alternatives considered

| Alternative | Why not |
|---|---|
| Licence TCG API at $49.99/mo (ADR-003) | Declined on cost; and it delivers the weaker product — aggregate prices, 3-day refresh, no sale history |
| eBay Browse only, no scraping | Legal and free, but **asking prices only**. FR-4 collapses and valuation loses its `sold` basis |
| Polite scraping — obey robots.txt, minimal rates | Offered and declined in favour of coverage. Would have reduced block risk without touching the terms exposure, which is the larger of the two |
| Manual price entry | Does not scale past a few hundred printings, and phase 2's coverage goal is 80% of owned printings weekly |

## Follow-ups

- [ ] Write the per-source terms review and record a risk owner, **before** the first enablement
- [ ] Decide the stop-versus-backoff threshold (open question, owner: Lars)
- [ ] Confirm the platform can issue `elestrals:admin`; the fallback is a `sub` allowlist, which is
      not an authorisation system
- [ ] Re-check TCGplayer API access annually — an approved key would supersede this ADR
- [ ] Revisit before the phase-3 marketplace charges a fee
