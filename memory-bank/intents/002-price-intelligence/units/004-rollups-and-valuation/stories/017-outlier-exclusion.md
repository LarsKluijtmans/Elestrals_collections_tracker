---
id: 017-outlier-exclusion
unit: 004-rollups-and-valuation
intent: 002-price-intelligence
status: complete
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 014-rollups-and-valuation
implemented: true
---

# Story: 017-outlier-exclusion

## User Story

**As a** collector
**I want** one absurd sale to not move my collection's value
**So that** a mis-priced listing or a joke auction does not become my portfolio number

## Acceptance Criteria

- [ ] **Given** a day's observations for a printing, **When** the rollup computes, **Then**
      observations beyond 3× the interquartile range are excluded from median and mean
- [ ] **Given** an excluded observation, **When** it is excluded, **Then** it is **flagged, not
      deleted**, and remains readable
- [ ] **Given** exclusions, **When** an admin views the price distribution, **Then** the excluded
      points are drawn distinctly from the kept ones
- [ ] **Given** fewer than four observations, **When** the rollup computes, **Then** no exclusion is
      attempted — an IQR over three points is not a statistic
- [ ] **Given** exclusions happened, **When** the rollup row is written, **Then** the observation
      count reflects what was **kept**, so confidence is computed on the data actually used
- [ ] **Given** the same day recomputed, **When** it runs again, **Then** the same points are
      excluded — the rule is deterministic

## Technical Notes

3× IQR rather than standard deviations: card prices are not normally distributed, and a
standard-deviation rule on a skewed distribution excludes the wrong tail.

Flagged rather than deleted, for two reasons. A silently dropped point is indistinguishable from one
that never existed, which makes the rollup unauditable; and under ADR-004 the excluded points are
themselves a signal — a source that suddenly produces many outliers is more likely to be broken than
the market is to have gone strange.

Applied per printing × condition × day. Across conditions it would exclude legitimate Heavily Played
prices as outliers of a Near Mint distribution.

## Dependencies

### Requires
- 016-daily-rollup-job

### Enables
- 029-price-distribution-and-source-agreement — which draws what this excluded

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Every observation identical | IQR is zero; nothing is excluded |
| Two clusters at very different prices | Both may survive; the median sits between them and the count tells the user the data is thin. Better than picking a cluster |
| A genuinely rare card selling for a genuinely high price | Excluded if it is a lone outlier, and visible as excluded. This is the accepted cost of the rule |
| An entire day of outliers from one broken source | Nothing excluded — they are the distribution. Caught by source agreement (story 029), not here |

## Out of Scope

- Per-source weighting of outliers
- Manual exclusion of a specific observation
