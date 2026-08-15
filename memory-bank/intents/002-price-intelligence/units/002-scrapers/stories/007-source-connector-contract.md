---
id: 007-source-connector-contract
unit: 002-scrapers
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 011-scraper-connectors
implemented: false
---

# Story: 007-source-connector-contract

## User Story

**As a** developer
**I want** one contract every source implements
**So that** adding a source is one file and one config row, and nothing downstream ever sees a
source-specific shape

## Acceptance Criteria

- [ ] **Given** the contract, **When** a connector implements it, **Then** it provides exactly
      `describe()`, `discover(query, limit)` and `recheck(external_ids)`
- [ ] **Given** any connector, **When** `discover` returns, **Then** the results are canonical
      `RawListing` values — no source-specific dict reaches the matcher
- [ ] **Given** a new source, **When** it is added, **Then** it takes one file in `harvest/sources/`
      and one row in `price_sources`, with no change anywhere else in the codebase
- [ ] **Given** a connector, **When** `describe()` is called, **Then** it declares its host, access
      mode, and whether it reports completed sales — and it can be called without credentials, so
      listing sources does not require configuring them
- [ ] **Given** a connector that cannot look up a listing by id, **When** it declares
      `supports_recheck = False`, **Then** the light scan skips its re-check phase and says so in
      the run rather than silently doing nothing
- [ ] **Given** a source class needing per-run state (a token, a cached catalog page), **When** a
      run starts, **Then** it gets a fresh connector instance — instances are never shared across
      runs

## Technical Notes

The registry holds **factories, not instances**. A connector is stateful for the length of a run —
it holds an HTTP client carrying that source's rate-limit bucket, and possibly a token with an
expiry. Sharing one instance across concurrent runs would share the bucket, which is the one thing
a rate limiter must not do.

`describe()` returning a descriptor that declares `reports_sold` is load-bearing rather than
documentary: story 015 checks a source's *configuration* against it, so a connector cannot
manufacture a sale by claiming one.

Money crosses this boundary as integer cents plus an explicit currency, parsed through `Decimal`
from the string the source actually sent. Never `float(x) * 100` — 19.99 is not representable in
binary and rounds wrong often enough to matter across a million rows.

## Dependencies

### Requires
- 006-rate-limiting-and-identification — every connector reaches the network through it

### Enables
- 008-deep-scan, 009-light-scan
- 010-connector-fixtures-and-drift-detection

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A source has no price on a result | The result is dropped, not defaulted to zero. A zero-priced observation is a wrong one, and it drags every median it touches |
| A source paginates differently from the others | Its own concern, inside its own file. `discover(query, limit)` is the only contract |
| A source needs credentials that are not configured | `describe()` still works; `discover()` raises a configuration error naming the missing key |
| A connector returns a listing with no external id | Dropped — without it there is no dedupe key and no way to re-check it |

## Out of Scope

- The scan modes themselves (stories 008, 009)
- Matching (unit 003)
