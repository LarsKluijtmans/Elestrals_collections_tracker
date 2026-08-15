---
unit: 005-admin-console
intent: 002-price-intelligence
phase: inception
status: ready
created: '2026-08-15T14:55:00Z'
updated: '2026-08-15T14:55:00Z'
---

# Unit Brief: admin-console

## Purpose

The surface where a human decides whether any of this is trustworthy. Admins — and only holders of
the `elestrals:admin` scope — can see every listing the harvester holds, every run it made, why each
listing matched or did not, how coverage and match quality are trending, and where two sources
disagree. From the same place they start and stop both scans.

This unit exists because of the decision that raw harvest data is admin-only, and that decision
exists because scraped data has to be judged before anything is built on it. The console is the
means of judging.

## Scope

### In Scope
- `elestrals:admin` authorisation, as one dependency every admin route shares
- The SPA admin section: code-split, gated, not rendered for a non-admin
- Listing explorer: filter, inspect, follow to source, see the match note
- Run history and per-source health: counters, accept-rate trend, quarantine state, kill switch
- Trigger and stop a deep or light scan, with live counters
- Coverage and match-quality analysis
- Price distribution and source disagreement

### Out of Scope
- Manually correcting a wrong match — scoped out at Checkpoint 1; it is its own story set
- CSV export and saved queries — same
- Anything a non-admin can see (unit 006)
- Changing a source's terms review or risk owner from the UI. Accepting a risk is a deliberate act
  and belongs in a migration or a CLI command with a written note, not behind a button

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-14 | Admin authorisation | Must |
| FR-15 | Admin data explorer | Must |
| FR-16 | Admin analysis | Must |
| FR-17 | Run the scrapers from the dashboard | Must |
| FR-12 | Harvest operations console | Must |

---

## Domain Concepts

### Key Entities
Read-only views over unit 001–004 entities: `PriceSource`, `HarvestRun`, `MarketListing`,
`PriceObservation`. This unit adds no persistent domain entity of its own, which is deliberate — a
console that stores its own state starts disagreeing with the pipeline it describes.

### Key Operations
| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `require_admin()` | The gate, shared by every admin route | validated JWT | principal, or 403 |
| `list_listings(filters)` | The explorer's query | source, run, mode, status, matched, kind, confidence band | page of listings |
| `source_health()` | Per-source operational picture | — | last run per mode, counters, accept-rate trend, quarantine state |
| `trigger_scan(source, mode)` | Start a run, return immediately | source, mode | run id, or 409 if one is running |
| `stop_scan(run)` | End a running scan `partial` with what it had | run id | run |
| `coverage_over_time()` | Tracked printings with a recent observation | window | series |
| `match_quality()` | Accept rate and top rejection reasons | source, mode, window | series + grouped counts |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 7 |
| Must Have | 7 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 023-admin-scope-authorisation | One gate, every route, no filtered 200s | Must | Planned |
| 024-admin-shell-and-routing | An admin section a non-admin never downloads | Must | Planned |
| 025-listing-explorer | See everything, and why it matched | Must | Planned |
| 026-run-history-and-health | Is the pipeline healthy, or just quiet? | Must | Planned |
| 027-trigger-and-watch-a-scan | Run both scrapers without a shell | Must | Planned |
| 028-coverage-and-match-quality | Is this data good enough to show anyone? | Must | Planned |
| 029-price-distribution-and-source-agreement | Do the sources agree, and what did we drop? | Must | Planned |

---

## Dependencies

### Depends On
| Unit | Reason |
|------|--------|
| 003-matching-and-observations | Stories 023–027 need listings and runs to display |
| 004-rollups-and-valuation | Stories 028–029 compare rollups and drawn outliers |
| intent 001 / 001-platform-foundation | JWT validation, the SPA shell the admin section mounts into |

### Depended By
| Unit | Reason |
|------|--------|
| — | Nothing depends on this unit. It is the judgement gate, not a dependency |

### External Dependencies
| System | Purpose | Risk |
|--------|---------|------|
| Platform token issuance | must carry `elestrals:admin` | **Medium** — unconfirmed. The fallback is a `sub` allowlist, which is not an authorisation system. Open question, owner Lars, due before this unit |

---

## Technical Context

### Suggested Technology
Admin routes live on `harvest-api` under `/api/v1/admin/*`, guarded by one FastAPI dependency —
mirroring the phase-1 `require_operator` pattern, which already carries the note that it is
provisional until the platform exposes app roles. The SPA admin section is a lazy-loaded route
bundle; the gate is checked before the chunk is requested, so a non-admin never downloads the code.
Trigger returns `202` with a run id, matching the phase-1 admin import endpoint. Live counters poll
the run detail endpoint; no websocket for one operator watching one run.

### Integration Points
| Integration | Type | Protocol |
|-------------|------|----------|
| SPA → `harvest-api` | API | REST `/api/v1/admin/*`, Bearer token |
| `harvest-api` → Celery | job control | Redis |

### Data Storage
None of its own. Every view is a query over units 001–004.

---

## Constraints

- **`403`, never a filtered `200`.** A response shaped like success with the interesting fields
  removed leaks the shape of what the caller cannot see, and trains the frontend to render an empty
  state that means "forbidden".
- **The gate is one dependency, used by every admin route.** A per-route check is a check a new
  route can forget.
- **The scope is read from the validated JWT only** — never from a body, query parameter or header.
- **Not rendered, not merely hidden.** Hiding an admin section client-side leaves the code and the
  route in the bundle for anyone who opens the network tab.
- **A second run of the same source and mode is refused, not queued.** Silently queueing makes an
  admin press the button twice and wonder why nothing happened.
- **The trigger path and the scheduled path are the same code.** Two paths drift, and the one that
  drifts is the one nobody runs by hand.
- **No source credential reaches the browser.** The UI asks `harvest-api` to run something; it never
  holds a key.
