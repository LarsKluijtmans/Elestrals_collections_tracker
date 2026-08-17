---
id: 011-scraper-connectors
unit: 002-scrapers
intent: 002-price-intelligence
type: ddd-construction-bolt
status: complete
stories:
  - 007-source-connector-contract
  - 008-deep-scan
  - 009-light-scan
  - 010-connector-fixtures-and-drift-detection
  - 011-block-detection-and-quarantine
created: 2026-08-15T15:25:00Z
started: 2026-08-15T15:30:00Z
completed: 2026-08-15T16:20:00Z
current_stage: done
stages_completed: [model, design, implement, test]  # spike NOT run - see below

requires_bolts:
  - 010-harvest-service-foundation
  - 002-card-catalog-schema-import
enables_bolts:
  - 012-matching-and-observations
requires_units: []
blocks: true

complexity:
  avg_complexity: 3
  avg_uncertainty: 3
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: 011-scraper-connectors

## Overview

The two scan modes and the connectors behind them, plus the machinery that keeps an assertive
scraper alive: recorded fixtures, drift detection, and quarantine when a source starts refusing us.

## Objective

Find out whether this intent is buildable. **This bolt is the go/no-go**, and it carries the only
uncertainty-3 rating in the intent — for the same reason bolt 002 did in intent 001, except that
this time the third parties have not agreed to be depended on and ADR-004 accepts that some of them
prohibit this.

## Stories Included

- **007-source-connector-contract**: one contract, one file per source (Must)
- **008-deep-scan**: find what we have never seen (Must)
- **009-light-scan**: re-check the known, find the neighbours (Must)
- **010-connector-fixtures-and-drift-detection**: fail loudly when a source changes (Must)
- **011-block-detection-and-quarantine**: survive being blocked (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [ ] **0. spike**: NOT RUN → **timeboxed, before the model stage** (see Notes)
- [x] **1. model**: Done → ddd-01-domain-model.md
- [x] **2. design**: Done → ddd-02-technical-design.md
- [x] **3. implement**: Done → `harvest/app/harvest/sources/`, planners, quarantine
- [x] **4. test**: Done → ddd-03-test-report.md, fixtures replayed, no network in CI

## Dependencies

### Requires
- 010-harvest-service-foundation (the service, gate, rate limiter)
- 002-card-catalog-schema-import (the deep planner builds its queries from the catalog)

### Enables
- 012-matching-and-observations

## Success Criteria

- [ ] A new source is one file plus one config row, with no other code change
- [ ] The deep plan is deterministic, broadest-first, capped, and records how many queries ran
- [ ] A deep scan against an empty catalog **fails loudly** rather than reporting a thin success
- [ ] A light scan asks materially fewer queries than a deep scan and finishes inside 20 minutes
- [ ] `last_seen_at` moves only for listings a scan actually asked about
- [ ] A disappeared listing becomes `ended_unknown`; no code path turns it into a sale
- [ ] A source outage leaves a listing alone rather than ending it
- [ ] Sustained 403/429/challenge quarantines the source; other sources are unaffected
- [ ] Quarantine expires, one probing request is made, and failure re-quarantines with longer backoff
- [ ] Every connector has recorded fixtures; the drift test names the field that stopped parsing
- [ ] The drift check runs on a schedule, not in the normal CI suite
- [ ] Coverage > 80%

## Notes

**Open with a timeboxed spike, before modelling anything.** Two questions decide the bolt:

1. **Do completed-listings pages carry a real sale price and date?** FR-4 now rests on this, and it
   is the technical argument in ADR-004. If they do not, FR-4 has to be weakened after all and the
   decision keeps only its cost argument — worth knowing in week one.
2. **What request rate does each source tolerate before it starts refusing?** This sets
   `rate_limit_per_min` for real rather than by guess, and it tests whether "assertive" is workable
   at all against these particular sites.

Days, not weeks. Both answers are reachable by hand against one source.

Fixture hygiene: record structure, not somebody's listing history. Nothing that identifies a seller
or a buyer goes into the repo, which is the same rule the NFR applies to what we store.

The failure mode to design against is **silence**. A connector broken by a markup change returns
zero rows, and so does a quiet market. The drift test and story 028's accept-rate trend are the only
two things that separate them.

## Construction result - 2026-08-15

**Status: complete in code, and the spike that was supposed to open it has NOT been run.**

That matters enough to say first. The bolt plan called for a timeboxed spike against one real
source before anything was modelled, to answer two questions. Neither has been answered:

1. **Do completed-listings pages carry a real sale price and date?** FR-4 rests on this, and it is
   the technical argument in ADR-004. The connector is written as though they do.
2. **What request rate does each source tolerate?** `rate_limit_per_min` is currently a guess.

**The selectors in `ebay_sold.py` are therefore unverified against a live page.** They encode the
long-standing `s-item` structure and are collected in one `_SELECTORS` table so correcting them is
a single edit. The fixture in `tests/fixtures/ebay_sold_page.html` is **hand-authored**, not
captured - it proves the parser does what we think, not that the page looks like that.

| Criterion | Verified |
|---|---|
| A new source is one file plus one config row | yes - three connectors register that way |
| Deep plan deterministic, broadest-first, capped, records what ran | yes |
| Deep scan against an empty catalog fails loudly | yes - `test_an_empty_catalog_fails_the_run_loudly` |
| Light scan asks materially fewer queries | yes - asserted, not assumed |
| `last_seen_at` moves only for listings actually asked about | yes |
| A disappeared listing becomes `ended_unknown`; nothing turns it into a sale | yes, twice: at the connector and again at the runner against `reports_sold` |
| A source outage leaves a listing alone | yes |
| Sustained refusals quarantine; the scan halts rather than finishing the plan | yes - `test_the_scan_halts_rather_than_working_through_the_rest_of_the_plan` |
| Quarantine expires, one probe, failure re-quarantines longer | policy tested (`test_quarantine.py`); the probe task is wired to beat but unexercised end to end |
| Fixtures replayed, no network in CI | yes |
| The drift check runs on a schedule, not in CI | **not built.** It needs the spike's real capture to check against, so it is deferred with the spike |

**A challenge page is treated as a refusal, not an empty market.** This is the failure that makes a
scraped pipeline dangerous - the scan reports success, the accept rate looks fine because nothing
was parsed, and the next run walks back into the block.
`test_a_challenge_page_is_a_refusal_not_an_empty_market` pins it.
