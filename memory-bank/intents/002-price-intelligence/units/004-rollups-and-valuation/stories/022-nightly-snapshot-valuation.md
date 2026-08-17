---
id: 022-nightly-snapshot-valuation
unit: 004-rollups-and-valuation
intent: 002-price-intelligence
status: complete
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 014-rollups-and-valuation
implemented: true
---

# Story: 022-nightly-snapshot-valuation

## User Story

**As a** collector
**I want** my portfolio chart to start on the day I joined rather than the day prices arrived
**So that** the history phase 1 has been quietly recording becomes visible

## Acceptance Criteria

- [ ] **Given** the nightly job, **When** it runs, **Then** each user's current collection value is
      written onto that day's `collection_snapshots` row
- [ ] **Given** existing snapshots recorded before phase 2, **When** the back-fill runs, **Then**
      each is valued using the rollups **for its own day**, not today's
- [ ] **Given** a snapshot day with no rollup data, **When** the back-fill runs, **Then** the value
      is left null and the chart breaks at that day rather than interpolating
- [ ] **Given** the back-fill, **When** it runs, **Then** it is re-runnable and produces the same
      values for the same days
- [ ] **Given** a user with no holdings on a day, **When** it is valued, **Then** the value is zero,
      which is a true statement about an empty collection

## Technical Notes

The distinction in the third criterion matters: **zero holdings is genuinely zero; unpriced holdings
are not.** Story 020's rule applies to the second case only, and conflating them would either erase
legitimate zeros or invent values for unpriced items.

Valuing a past snapshot with today's rollups would make the whole history move every night, which is
the same failure as using today's FX rate for a year-old sale (story 018).

Rollups only reach back to the day the harvester started producing observations. Before that, values
are null and the chart honestly starts later than the counts do — the counts are still real history
and worth showing.

## Dependencies

### Requires
- 020-collection-valuation
- intent 001 — `collection_snapshots`, which phase 1 has been writing since launch

### Enables
- 021-portfolio-history-and-pl

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A user joined before phase 2 | Their counts exist; values start when rollups do, and the chart says so |
| A user deleted their account | Their snapshots go with them, as in phase 1 |
| The job runs twice in one night | Idempotent — the same day's value is recomputed, not appended |
| Rollups for a past day are later corrected | The back-fill can be re-run for that day; snapshots are a projection too |
| A user with 50k holdings | The job is batched; it is nightly and out of band, so it may take its time |

## Out of Scope

- Per-item historical values. Snapshots are collection-level
- Recording history for slices or saved views
