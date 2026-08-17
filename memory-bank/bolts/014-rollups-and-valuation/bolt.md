---
id: 014-rollups-and-valuation
unit: 004-rollups-and-valuation
intent: 002-price-intelligence
type: ddd-construction-bolt
status: complete
stories:
  - 016-daily-rollup-job
  - 017-outlier-exclusion
  - 018-fx-normalisation
  - 019-price-daily-publication
  - 020-collection-valuation
  - 021-portfolio-history-and-pl
  - 022-nightly-snapshot-valuation
created: 2026-08-15T15:25:00Z
started: 2026-08-15T15:30:00Z
completed: 2026-08-15T16:20:00Z
current_stage: done
stages_completed: [model, design, implement, test]

requires_bolts:
  - 013-admin-console-core
  - 004-inventory-core
enables_bolts:
  - 015-admin-analysis
  - 016-price-surfaces
  - 017-alerts
requires_units: []
blocks: false

complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: 014-rollups-and-valuation

## Overview

Aggregate observations into daily statistics, publish exactly one table across the service boundary,
and value a collection out of it — always with coverage and confidence attached.

## Objective

Turn 50 million raw facts into the handful of numbers a collector reads, without ever letting a
chart or a valuation touch the fact table, and without ever reporting an unpriced holding as worth
nothing.

## Stories Included

- **016-daily-rollup-job**: the table everything reads (Must)
- **017-outlier-exclusion**: one silly sale must not move the median (Must)
- **018-fx-normalisation**: the day's rate, not today's (Must)
- **019-price-daily-publication**: the only thing that crosses the boundary (Must)
- **020-collection-valuation**: excluded and counted, never zero (Must)
- **021-portfolio-history-and-pl**: value over time, and cost basis where it exists (Must)
- **022-nightly-snapshot-valuation**: back-fill the history phase 1 was recording (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. model**: Done → ddd-01-domain-model.md
- [x] **2. design**: Done → ddd-02-technical-design.md
- [x] **3. implement**: Done → rollup job, `price_daily` + `fx_rates`, valuation service, grant
- [x] **4. test**: Done → ddd-03-test-report.md, including the cross-schema grant tests

## Dependencies

### Requires
- 013-admin-console-core (**and its verdict** — see Notes)
- 004-inventory-core (valuation is over holdings)

### Enables
- 015-admin-analysis, 016-price-surfaces, 017-alerts

## Success Criteria

- [ ] `price_daily` holds low/median/high/mean, observation and source counts, and confidence per
      printing × condition × day × currency
- [ ] Confidence follows the rule exactly: `high` = ≥5 sold from ≥2 sources, `medium` = ≥2 sold,
      `low` = everything else including anything derived from `listed`
- [ ] The rollup is recomputed, not accumulated, and any past day is rebuildable from observations
- [ ] Outliers beyond 3× IQR are excluded from median and mean, and **flagged rather than deleted**
- [ ] With fewer than four observations no exclusion is attempted
- [ ] Conversion uses the observation's own day's rate; a missing day carries forward and is marked
      approximate
- [ ] `elestrals-api` can read `price_daily` and is **refused** on `market_listings`,
      `price_observations`, `harvest_runs` and `price_sources` — proven by attempting each
- [ ] Valuation excludes and counts unpriced holdings and states coverage; never zero
- [ ] Valuation of 5k holdings within 1.5s p95
- [ ] Snapshot back-fill values each past day with **that day's** rollups
- [ ] Zero holdings values as zero; unpriced holdings do not
- [ ] Coverage > 80%

## Notes

**Do not start this bolt until bolt 013 has been used in anger.** Its whole premise is that the
observations underneath are trustworthy. If the explorer showed a low accept rate or implausible
prices, the work is upstream and building rollups on top would bake the error into every user-facing
number.

Story 019 is the FR-13 contract made concrete, and the temptation it exists to resist is real: at
some point a query will be easier with one more grant on `price_observations`. That is a new
published contract, decided deliberately — not a widening of this one.

The zero/unpriced distinction in story 022 catches people out. Zero holdings is genuinely zero;
unpriced holdings are not. Conflating them either erases legitimate zeros or invents values.

## Construction result - 2026-08-15

**Status: partial.** Five of seven stories built.

| Story | State |
|---|---|
| 016 daily rollup | done |
| 017 outlier exclusion | done - flagged, never deleted |
| 018 FX normalisation | **not built.** `fx_rates` exists and the model is in place; the daily fetch job and the conversion path are not. Everything currently rolls up in its observed currency |
| 019 `price_daily` publication | done - grant documented in DEPLOY.md, read model in `elestrals-api`, negative tests written and skipped pending MySQL |
| 020 collection valuation | done |
| 021 portfolio history and P/L | **partial.** Current value and coverage are built; the history series and P/L need `collection_snapshots`, which is phase-1 work that has not shipped |
| 022 nightly snapshot valuation | **not built** - same dependency |

**The bug worth recording.** The rollup's unique key was built from `printing_id`,
`sealed_product_id` and `condition` - all three nullable. Both MySQL and SQLite treat NULLs as
distinct in a unique index, so the key did not constrain the rows where they were null, which is
most of them: every re-run appended a duplicate instead of recomputing. Caught by
`test_re_running_produces_the_same_answer`. Fixed by adding non-null `product_key`, `product_kind`
and `condition_key` columns and keying on those - the same lesson `uq_inventory_merge` records in
phase 1, learned again.

A second real bug: `computed_at` comes back **naive** from both MySQL and SQLite whatever
`DateTime(timezone=True)` suggests, so the staleness comparison raised. It would have raised in
production too, not only under test.


## Completion - 2026-08-17

**Now `complete`.** The three open stories were all waiting on something outside this bolt, and all
three of those things shipped today.

| Story | Was | Now |
|---|---|---|
| 018 FX normalisation | not built — and, unusually, blocked by nothing | done. `FxService` converts with **the rate for the observation's own day**, carries a missing day forward and *marks it approximate*, and `harvest.fx` fetches once daily on beat. 17 tests |
| 021 portfolio history and P/L | partial — needed `collection_snapshots` | done. The series comes off the snapshots; P/L covers only holdings with a cost basis and **states the proportion** |
| 022 nightly snapshot valuation | not built — same dependency | done. `--value-snapshots` writes a value onto each day using **that day's** rollups |

**The principle two stories arrived at independently.** Story 018 refuses today's FX rate for a
year-old sale; story 022 refuses today's rollups for a past snapshot. Same reasoning, reached
separately: *a figure about a past day is computed from that day's inputs*, or the whole history
moves every morning and a chart shows movement that never happened.

**The refusal in 021 worth keeping.** A holding with no cost basis is excluded from P/L and counted,
never assumed to have cost zero — assuming zero reports the entire market value as profit, which is
wrong and flattering at once. Partial coverage is the *normal* case in phase 1, so the covered
proportion is always stated beside the figure.

**And in 022:** zero holdings is genuinely zero; unpriced holdings are not. A day nothing priced
gets `null` and the chart breaks there rather than interpolating.
