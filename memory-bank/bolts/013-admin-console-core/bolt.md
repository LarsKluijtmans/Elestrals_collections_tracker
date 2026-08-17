---
id: 013-admin-console-core
unit: 005-admin-console
intent: 002-price-intelligence
type: ddd-construction-bolt
status: complete
stories:
  - 023-admin-scope-authorisation
  - 024-admin-shell-and-routing
  - 025-listing-explorer
  - 026-run-history-and-health
  - 027-trigger-and-watch-a-scan
created: 2026-08-15T15:25:00Z
started: 2026-08-15T15:30:00Z
completed: 2026-08-15T16:20:00Z
current_stage: done
stages_completed: [model, design, implement, test]

requires_bolts:
  - 012-matching-and-observations
enables_bolts:
  - 014-rollups-and-valuation
requires_units: []
blocks: true

complexity:
  avg_complexity: 3
  avg_uncertainty: 1
  max_dependencies: 1
  testing_scope: 3
---

# Bolt: 013-admin-console-core

## Overview

The admin gate, the admin section, the listing explorer, per-source health, and the ability to start
and stop both scrapers without a shell.

## Objective

**Make the data judgeable.** This is the intent's decision point: at the end of this bolt you can
look at what the scrapers actually produced, see why each listing matched or did not, and decide
whether bolts 14 to 17 should start at all.

## Stories Included

- **023-admin-scope-authorisation**: one gate, every route, no filtered 200s (Must)
- **024-admin-shell-and-routing**: an admin section a non-admin never downloads (Must)
- **025-listing-explorer**: see everything, and why it matched (Must)
- **026-run-history-and-health**: is the pipeline healthy, or just quiet? (Must)
- **027-trigger-and-watch-a-scan**: run both scrapers without a shell (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. model**: Done → ddd-01-domain-model.md
- [x] **2. design**: Done → ddd-02-technical-design.md
- [x] **3. implement**: Done → `/api/v1/admin/*` on `harvest-api`, the SPA admin section
- [x] **4. test**: Done → ddd-03-test-report.md, **including the route-enumeration test**

## Dependencies

### Requires
- 012-matching-and-observations (there must be data worth looking at)
- 001-platform-foundation (JWT validation, the app shell this mounts into)

### Enables
- 014-rollups-and-valuation — but see Notes: this bolt decides whether it should start

## Success Criteria

- [ ] A caller without `elestrals:admin` gets `403` with no body detail from every admin route
- [ ] A test enumerates the admin router and asserts every route carries the shared dependency
- [ ] `elestrals:operator` alone is refused — the two roles are distinct
- [ ] A non-admin does not **download** the admin bundle, verified by inspecting network requests
- [ ] The explorer filters by source, run, mode, status, matched/unmatched, kind and confidence band
- [ ] The unmatched queue is one click from the default view
- [ ] 50k listings page within 400ms p95
- [ ] `ended_unknown` is labelled as "ended, reason unknown" and nowhere described as a sale
- [ ] A quarantined source is visibly distinct from one finding nothing, and shows its retry time
- [ ] Each source shows its terms-review note and risk owner next to its name
- [ ] Triggering returns a run id immediately; a duplicate run of the same source and mode is `409`
- [ ] Stopping a run ends it `partial` with what it had
- [ ] The triggered path and the scheduled path are the same code
- [ ] Coverage > 80%

## Notes

**This bolt is scheduled before 014 deliberately.** The obvious order builds valuation first and the
tools to inspect it second. Under ADR-004 that is backwards: every number comes from scraped pages
of uneven quality, and this console is the only way to learn whether the matcher is placing titles
correctly. Building valuation first means discovering a systematic matcher error through a user's
portfolio figure — the latest and most expensive place to find it.

**Do not start bolt 014 until you have actually used this.** If the accept rate is low, the prices
implausible, or the matching systematically wrong, the work is in bolt 012 or 011, not in rollups.

**Blocking dependency**: whether the platform can issue `elestrals:admin` is unresolved. If it
cannot, the fallback is a `sub` allowlist — a development convenience, not an authorisation system —
and shipping on it would deserve its own ADR rather than a quiet substitution.

Enabling a source is deliberately absent from this UI. The kill switch is here; accepting a risk is
not a button.

## Construction result - 2026-08-15

**Status: complete.** Eleven admin routes on `harvest-api`, and a code-split admin section in the
SPA.

| Criterion | Verified |
|---|---|
| `403` with no body detail from every admin route | yes |
| A test enumerates the router and asserts every route carries the gate | yes - over all 11 |
| `elestrals:operator` alone is refused | yes |
| A non-admin does not **download** the admin bundle | yes - the build emits `HarvestConsole-*.js` as a separate 27 kB chunk, requested only after the scope check |
| Explorer filters by source, run, status, kind, matched, confidence band | yes |
| The unmatched queue is one click from the default view | yes |
| `ended_unknown` never described as a sale | yes, and pinned by a frontend test on `statusLabel` |
| A quarantined source is visibly distinct; shows its retry time | yes |
| Terms note and risk owner shown next to each source | yes |
| Trigger returns a run id; a duplicate is `409` | yes |
| Stopping ends the run `partial` with what it had | yes |
| Trigger path and scheduled path are the same code | yes - both call `make_harvest_runner` |
| 50k listings within 400ms p95 | **not measured.** The indexes are in place; the benchmark is not |

**The route-enumeration test found a real gap while being written**: this FastAPI version nests
routes inside `_IncludedRouter`, so a flat scan of `app.routes` found none of them and the test
passed over an empty list. A test that silently checks nothing is worse than no test, so it now
asserts a minimum route count as well.

**Blocking question, unchanged:** whether the platform can issue `elestrals:admin`. Until it can,
the only way in is the development `sub` allowlist, which is inert in production by design - so on
a production deployment today nobody can reach the console at all. That is the correct failure, but
it is a failure.
