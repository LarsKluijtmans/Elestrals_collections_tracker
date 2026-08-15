---
id: 008-deep-scan
unit: 002-scrapers
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 011-scraper-connectors
implemented: false
---

# Story: 008-deep-scan

## User Story

**As an** admin
**I want** a scan that asks every question the catalog can generate
**So that** Elestrals items we have never seen — including products missing from our own catalog —
get found

## Acceptance Criteria

- [ ] **Given** the catalog, **When** a deep plan is built, **Then** it contains a brand sweep,
      one query per sealed format, one per catalog sealed product, one per set name and code, and
      one per card name — deduplicated
- [ ] **Given** the plan, **When** it is ordered, **Then** the broadest queries come first, so a
      plan truncated by its cap still asks the questions that discover unknown products
- [ ] **Given** the same catalog, **When** the plan is built twice, **Then** it is identical — a plan
      that reshuffles nightly asks a different arbitrary subset each time and never covers the tail
- [ ] **Given** a plan larger than the cap, **When** it runs, **Then** `harvest_runs.queries` records
      how many actually ran, so truncation is visible rather than assumed
- [ ] **Given** a listing returned for the first time, **When** it is stored, **Then** it is counted
      as `discovered` and written to `market_listings` with its first-seen run
- [ ] **Given** a listing already known, **When** it is returned again, **Then** it is updated, not
      duplicated, and not counted as discovered
- [ ] **Given** one query failing, **When** the scan continues, **Then** the remaining queries run
      and the run ends `partial` naming the failure
- [ ] **Given** an empty catalog, **When** a deep scan runs, **Then** it fails loudly rather than
      quietly running four generic sweeps and reporting success

## Technical Notes

Every query is anchored on the brand term. Without it, a search for a card name returns the whole
trading-card market and the matcher spends the run rejecting other games.

Each query carries a `reason` — brand sweep, catalog set, catalog card — which is what makes a
400-query run readable afterwards instead of an undifferentiated wall.

Card-name queries come last: the most numerous and the most redundant, since a set sweep already
returns many of them. They earn their place by catching the cards nobody lists with a set name,
which on a marketplace is most of them.

The empty-catalog failure is reachable: ADR-001 left `FE01.csv` empty on purpose, and a deep scan
built from an empty catalog looks like a successful thin run.

## Dependencies

### Requires
- 007-source-connector-contract
- 005-run-lifecycle-and-sweeper
- intent 001 / 002-card-catalog — the plan is built from it

### Enables
- 012-title-to-printing-matcher — there is nothing to match until this runs
- 025-listing-explorer

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Catalog grows past the query cap | Truncation happens at the narrowest queries; `queries` shows it; the cap is configuration |
| A source returns the same listing for many queries | Stored once, via `UNIQUE (source_id, external_id)`; counted `discovered` once |
| A source returns a `total` larger than the page it sent | Paging stops on the short page as well as on `total`, or it pages forever |
| A previously-ended listing reappears | Set back to `active` and its `ended_at` cleared, or the row has an end date in its own past |
| Deep scan exceeds 4 hours | Ends when the plan ends; the NFR breach is visible in the run's duration and is a signal to lower the cap |

## Out of Scope

- Re-checking known listings (story 009)
- Deciding what any listing *is* (unit 003)
