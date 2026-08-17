---
unit: 004-rollups-and-valuation
intent: 002-price-intelligence
phase: inception
status: ready
created: '2026-08-15T14:55:00Z'
updated: '2026-08-15T14:55:00Z'
---

# Unit Brief: rollups-and-valuation

## Purpose

Turn 50 million raw observations into the handful of numbers a collector actually reads, publish
them across the service boundary, and value a collection out of them. Two hard rules run through the
whole unit: **charts and valuation never touch the fact table**, and **an item with no price is
excluded and counted, never treated as zero**.

This unit also builds the one contract between the two backends. `price_daily` is the only thing
`elestrals-api` may read out of `elestrals_harvest`, and the grant enforces it.

## Scope

### In Scope
- The nightly rollup: low / median / high / mean, observation and source counts, confidence
- IQR-based outlier exclusion, with excluded points flagged rather than deleted
- FX rates and per-day conversion
- `price_daily` publication and the read grant that limits the collection backend to it
- Collection valuation over any slice, with coverage and confidence stated
- Portfolio history and P/L from `collection_snapshots`
- Back-filling snapshot values from the day phase 1 started recording counts

### Out of Scope
- Drawing any of it (unit 006)
- Alerting on it (unit 007)
- The admin analysis views (unit 005) — they read observations directly, not rollups

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-5 | Daily rollups | Must |
| FR-6 | Currency normalisation | Must |
| FR-8 | Collection valuation | Must |
| FR-9 | Portfolio over time and P/L | Must |

---

## Domain Concepts

### Key Entities
| Entity | Description | Attributes |
|--------|-------------|------------|
| PriceDaily | The rollup everything reads | `printing_id`, `sealed_product_id`, `condition`, `day`, `currency`, `low_cents`, `median_cents`, `high_cents`, `mean_cents`, `observation_count`, `source_count`, `confidence` |
| FxRate | One day's conversion | `day`, `base`, `quote`, `rate` |
| Valuation | A slice of a collection, priced | `total_cents`, `currency`, `valued_items`, `unvalued_items`, `confidence` |

### Key Operations
| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `roll_up(day)` | Aggregate a day's observations | day | `price_daily` rows |
| `exclude_outliers(points)` | Drop beyond 3× IQR, flag what was dropped | observations | kept + flagged |
| `convert(amount, day)` | Use the observation's day's rate, not today's | amount, currency, day | converted |
| `value(slice)` | Sum `quantity × median`, count what could not be priced | holdings, filters | valuation |

### Confidence rule
`high` = ≥ 5 sold observations from ≥ 2 sources in the window. `medium` = ≥ 2 sold observations.
`low` = anything else, **including anything derived from `listed` prices**. No figure renders
without it.

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
| 016-daily-rollup-job | The table everything reads | Must | Planned |
| 017-outlier-exclusion | One silly sale must not move the median | Must | Planned |
| 018-fx-normalisation | The day's rate, not today's | Must | Planned |
| 019-price-daily-publication | The only thing that crosses the boundary | Must | Planned |
| 020-collection-valuation | Excluded and counted, never zero | Must | Planned |
| 021-portfolio-history-and-pl | Value over time, and cost basis where it exists | Must | Planned |
| 022-nightly-snapshot-valuation | Back-fill the history phase 1 was recording | Must | Planned |

---

## Dependencies

### Depends On
| Unit | Reason |
|------|--------|
| 003-matching-and-observations | Rollups aggregate observations |
| intent 001 / 003-inventory-core | Valuation is over holdings |

### Depended By
| Unit | Reason |
|------|--------|
| 005 (stories 028–029) | Source agreement compares rollups |
| 006, 007 | Every user-facing figure and every alert reads `price_daily` |

### External Dependencies
| System | Purpose | Risk |
|--------|---------|------|
| FX rate source | one call a day | Low — a missed day carries the previous rate forward and marks the conversion approximate |

---

## Technical Context

### Suggested Technology
The rollup is a Celery beat job in `harvest-api`, computing per printing × condition × day ×
currency. `price_daily` is exposed to the collection backend as a granted read on that one table (or
a view over it), never as a join into anything else. Valuation lives in `elestrals-api`, because it
joins the user's inventory — which the harvester cannot read.

### Integration Points
| Integration | Type | Protocol |
|-------------|------|----------|
| `elestrals_harvest.price_daily` | outbound read, from `elestrals-api` | MySQL cross-schema, read-only grant |
| FX provider | outbound | HTTPS, once daily |

### Data Storage
| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| `price_daily` | SQL | 20M at 12 months | permanent |
| `fx_rates` | SQL | ~1k/year | permanent |

---

## Constraints

- **The rollup is rebuildable from observations, always.** It is a projection, never a source of
  truth. Any bug found in it is fixed by recomputing, not by patching rows.
- **`sold` and `listed` are never mixed.** Valuation reads `sold`; a printing with only `listed`
  data is `low` by definition.
- **Unpriced items are excluded and counted**, and the count is shown: "412 of 500 items valued".
  Treating an unpriced holding as zero produces a number that is confidently wrong.
- **Excluded outliers are flagged, not deleted.** The admin analysis view (story 029) draws them,
  and a silently dropped point is indistinguishable from one that never existed.
- **The cross-schema read is exactly one table.** If a later feature needs more, that is a new
  published contract and a new grant — not a widened one.
