---
intent: 002-price-intelligence
phase: inception
status: bolts-planned
updated: 2026-08-15T15:15:00Z
---

# Price Intelligence - Bolt Plan

**8 bolts, 34 stories, 7 units.** Seven DDD bolts and one simple bolt. Numbering continues the
global sequence from intent 001, which ended at bolt 009.

## Bolt sequence

| # | Bolt | Unit | Stories | Type | Complexity | Uncertainty |
|---|---|---|---|---|---|---|
| 10 | `010-harvest-service-foundation` | 001 | 6 | DDD | 3 | 2 |
| 11 | `011-scraper-connectors` | 002 | 5 | DDD | 3 | **3** |
| 12 | `012-matching-and-observations` | 003 | 4 | DDD | 3 | 2 |
| 13 | `013-admin-console-core` | 005 | 5 | DDD | 3 | 1 |
| 14 | `014-rollups-and-valuation` | 004 | 7 | DDD | 3 | 2 |
| 15 | `015-admin-analysis` | 005 | 2 | DDD | 2 | 1 |
| 16 | `016-price-surfaces` | 006 | 4 | DDD | 2 | 1 |
| 17 | `017-alerts` | 007 | 1 | simple | 1 | 1 |

## Dependency graph

```text
010-harvest-service-foundation
   └─> 011-scraper-connectors
          └─> 012-matching-and-observations
                    └─> 013-admin-console-core        ← THE JUDGEMENT GATE
                              └─> 014-rollups-and-valuation
                                       ├─> 015-admin-analysis
                                       ├─> 016-price-surfaces
                                       └─> 017-alerts
```

Bolts 10 to 13 are strictly sequential and there is no useful way to parallelise them: there is
nothing to scrape without a service, nothing to match without listings, and nothing to judge without
matches. After bolt 14, three chains are independent — analysis, user surfaces, and alerts — and
parallelise cleanly if there is more than one pair of hands.

## Risk-driven ordering

The ordering is not the dependency graph's only valid topological sort. Two choices were made
deliberately:

**Bolt 13 comes before bolt 14.** The obvious order would be rollups → user surfaces → console,
finishing the product and then building the tools to inspect it. That order is wrong here. ADR-004
means every number in this intent comes from scraped pages of uneven quality, and the console is the
only way to find out whether the matcher is placing titles correctly. Building valuation first would
mean discovering a systematic matcher error through a user's portfolio figure, which is both the
latest and the most expensive place to find it.

**Bolt 11 is the go/no-go.** It carries the intent's only uncertainty-3 rating for the same reason
bolt 002 did in intent 001: it depends on third parties, and this time on third parties who have not
agreed to be depended on. ADR-004 accepts that some prohibit this and may block us. If the sources
cannot be read at a useful rate — or if a block arrives immediately and permanently — that is
knowable at the end of bolt 11, before three more bolts are built on the assumption.

**Bolt 11 should open with a timeboxed spike** against one real source, exactly as bolt 002 did:
fetch a handful of pages, confirm that completed-listings pages carry a real sale price and date
(the assumption FR-4 now rests on), and confirm the request rate that source tolerates. If completed
listings turn out not to carry sale data, FR-4 has to be weakened after all and ADR-004's technical
argument evaporates — leaving only the cost argument, which is worth knowing early.

## Milestones

| After bolt | The product can… | Worth showing to |
|---|---|---|
| 010 | deploy a second service that records runs and refuses uncleared sources | nobody — but every later bolt starts from a working, isolated service |
| **011** | **actually read the sources, or discover that it cannot** | **yourself — this is the go/no-go on the whole intent** |
| 012 | turn listings into prices attached to real SKUs | yourself, through the CLI |
| **013** | **be looked at, judged, and operated without a shell** | **yourself, seriously — this is where you decide whether the data is worth building on** |
| 014 | value a collection | yourself; still nothing user-facing |
| 015 | prove the data is good, or find out it is not | yourself, and anyone asking how you know |
| 016 | show collectors what their collection is worth | first external users |
| 017 | tell them when something moves | the same users, more usefully |

**Bolt 013 is the decision point of this intent.** If the explorer shows a low accept rate,
implausible prices or systematic mismatching, bolts 14 to 17 should not start until the matcher or
the connectors are fixed. Everything after 013 assumes the data is trustworthy; 013 is where that
assumption is tested rather than made.

**Bolt 016 is the minimum shippable increment for users.** Nothing before it is visible to a
collector, and that is intentional under ADR-004.

## Bolt types

Seven DDD bolts, because every one of them introduces or changes domain rules — the gate, the scan
modes, the matcher, the rollup, the authorisation boundary. `017-alerts` is a simple bolt: one story,
one table, evaluation appended to an existing job.

## What this plan assumes

| Assumption | If wrong |
|---|---|
| Completed-listings pages carry a real sale price and date | FR-4 weakens; ADR-004 keeps only its cost argument. **Tested in bolt 011's opening spike** |
| Sources tolerate an assertive rate before blocking | Coverage degrades to whatever survives quarantine; the intent still ships, thinner. Known by the end of bolt 011 |
| The platform can issue `elestrals:admin` | Bolt 013 falls back to a `sub` allowlist, which is not an authorisation system. **Open question, owner Lars, due before bolt 013** |
| The catalog is populated enough to match against | Bolt 012's accept rate collapses and the cause is visible in bolt 013. ADR-001's incomplete seed makes this reachable |

## Open questions that gate bolts

| Question | Gates | Owner |
|---|---|---|
| Can the platform issue `elestrals:admin`? | bolt 013 | Lars |
| At what point does a block become a stop rather than a backoff? | bolt 011 | Lars |
| Median or trimmed mean as the headline figure? | bolt 014 | Lars |
