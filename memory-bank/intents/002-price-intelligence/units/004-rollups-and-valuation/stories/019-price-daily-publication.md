---
id: 019-price-daily-publication
unit: 004-rollups-and-valuation
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 014-rollups-and-valuation
implemented: false
---

# Story: 019-price-daily-publication

## User Story

**As an** operator
**I want** exactly one table to cross between the two services
**So that** the boundary between them stays a boundary, and the raw harvest stays admin-only by
construction rather than by discipline

## Acceptance Criteria

- [ ] **Given** the `elestrals-api` MySQL user, **When** it selects from
      `elestrals_harvest.price_daily`, **Then** it succeeds
- [ ] **Given** the same user, **When** it selects from `market_listings`, `price_observations`,
      `harvest_runs` or `price_sources`, **Then** MySQL refuses it
- [ ] **Given** the same user, **When** it attempts any write to `price_daily`, **Then** MySQL
      refuses it
- [ ] **Given** a test suite against real MySQL, **When** it runs, **Then** it attempts each
      forbidden read and write and asserts the refusal
- [ ] **Given** `harvest-api` is down, **When** a price surface loads, **Then** it serves from
      `price_daily` unaffected — the rollup table is data, not a service call
- [ ] **Given** a schema change to `price_daily`, **When** it is made, **Then** it is additive; a
      column is never removed or repurposed without both services being ready

## Technical Notes

This story is the FR-13 contract, made concrete. `price_daily` is the entire interface between the
two backends: one granted read, one direction.

A grant rather than an API. An HTTP call would make the collection backend depend on the harvester's
availability, which is exactly what FR-13 exists to prevent — and it would put a network hop in the
p95 < 250ms price-tab budget. A cross-schema read of an indexed table has neither problem.

Additive-only because two services deploy independently. A removed column is an outage in whichever
service deploys second.

If a later feature needs more than `price_daily`, that is a **new published contract and a new
grant**, decided deliberately — not a widening of this one. The temptation to "just also grant
`price_observations` for one query" is the failure this story is written to prevent.

## Dependencies

### Requires
- 016-daily-rollup-job — there must be a table to publish
- 002-harvest-schema-and-grants — the grant model this extends by exactly one line

### Enables
- 020-collection-valuation
- Every story in units 006 and 007

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A developer needs observation-level data in the app | Refused by the grant. The answer is a new published projection, or the admin console |
| `price_daily` grows past comfortable join size | Indexed on `(printing_id, condition, day, currency)`; the read is a point lookup or a range, never a scan |
| Rollup job has never run | The table is empty; surfaces show honest empty states, not errors |
| Someone grants `elestrals_harvest.*` for convenience | Review failure, and the negative test fails |

## Out of Scope

- Any API between the services. There is deliberately none
- Replicating `price_daily` into `elestrals`. One copy, one owner
