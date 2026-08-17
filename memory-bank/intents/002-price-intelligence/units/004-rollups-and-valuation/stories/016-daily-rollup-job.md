---
id: 016-daily-rollup-job
unit: 004-rollups-and-valuation
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 014-rollups-and-valuation
implemented: false
---

# Story: 016-daily-rollup-job

## User Story

**As a** collector
**I want** a price chart that loads instantly and a valuation that does not scan millions of rows
**So that** the product is usable at the data volume it is designed for

## Acceptance Criteria

- [ ] **Given** a day's observations, **When** the rollup runs, **Then** `price_daily` holds low,
      median, high, mean, observation count and source count per printing × condition × day ×
      currency
- [ ] **Given** the rollup, **When** it computes confidence, **Then** `high` = ≥ 5 sold observations
      from ≥ 2 sources, `medium` = ≥ 2 sold, `low` = anything else **including anything derived from
      `listed` prices**
- [ ] **Given** the rollup has run before, **When** it runs again for the same day, **Then** the
      result is identical — it is a projection, recomputed rather than accumulated
- [ ] **Given** an arbitrary past day, **When** the rollup is asked to rebuild it, **Then** it can,
      from observations alone
- [ ] **Given** charts and valuation, **When** they read, **Then** they touch `price_daily` only and
      never `price_observations`
- [ ] **Given** the NFR budget, **When** the rollup runs, **Then** it completes within 20 minutes

## Technical Notes

A Celery beat job in `harvest-api`, running after the light scan's last cadence for the day.

Recomputed, never accumulated. A rollup that increments is a rollup that cannot be fixed by
re-running, and any bug found in it becomes a data migration.

`sold` and `listed` are aggregated into separate rows, never blended — a printing can have both, and
the UI chooses which to show and labels it.

Sealed products roll up the same way, keyed on `sealed_product_id` with a null condition.

## Dependencies

### Requires
- 015-sold-vs-listed-separation

### Enables
- 017-outlier-exclusion, 018-fx-normalisation, 019-price-daily-publication
- 020, 021, 022, and everything in units 006 and 007

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A day with no observations for a printing | No row. An absent day is absent, not zero |
| A day with exactly one observation | A row with count 1 and `low` confidence. Honest, and the UI shows the count |
| Observations arrive late for a past day | That day is recomputed on the next run; rollups are never final |
| Multiple currencies for one printing | Separate rows per currency; conversion is story 018's job at read time |
| The rollup crashes half way | Re-run recomputes; no partial state to reconcile |

## Out of Scope

- Excluding outliers (story 017) — layered on top
- Any chart (unit 006)
