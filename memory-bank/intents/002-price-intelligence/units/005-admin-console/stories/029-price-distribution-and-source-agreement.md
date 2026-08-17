---
id: 029-price-distribution-and-source-agreement
unit: 005-admin-console
intent: 002-price-intelligence
status: complete
priority: must
created: '2026-08-15T15:00:00Z'
assigned_bolt: 015-admin-analysis
implemented: true
---

# Story: 029-price-distribution-and-source-agreement

## User Story

**As an** admin
**I want** to see the spread of prices behind a median and whether the sources agree with each other
**So that** I can catch a source that is quietly wrong before its numbers reach anyone's portfolio

## Acceptance Criteria

- [ ] **Given** a printing and a day, **When** I open its distribution, **Then** I see every
      observation behind the rollup, with the excluded outliers drawn distinctly
- [ ] **Given** a distribution, **When** it renders, **Then** `sold` and `listed` observations are
      visually separate and never merged into one cloud
- [ ] **Given** a printing covered by two or more sources, **When** I view agreement, **Then** their
      medians are compared and the disagreement is quantified
- [ ] **Given** a source consistently higher or lower than the others, **When** the view renders,
      **Then** it is identifiable as a systematic offset rather than as noise
- [ ] **Given** a printing covered by one source, **When** I view agreement, **Then** it says so —
      single-source coverage is a fact about confidence, not a gap in the view
- [ ] **Given** any observation in the distribution, **When** I click it, **Then** I reach its
      `source_url`

## Technical Notes

This reads `price_observations` directly rather than rollups — it is the one view whose job is to
explain what the rollup did, so it has to see what the rollup saw. It is also why the fact table's
`(printing_id, observed_at)` index exists.

Source agreement is the strongest available check on a scraped pipeline. A connector that is subtly
wrong — parsing the wrong price field, picking up shipping, reading a different currency — produces
plausible numbers that only look wrong next to another source's. Under ADR-004 there is no licensed
reference to check against, so cross-source comparison is the reference.

Systematic offset versus noise is the distinction worth designing for: a source 8% high on every
printing is a bug in that connector; a source scattered around the others is a thinner market.

`sold` and `listed` kept visually apart, always. Merging them here would undo story 015 in the one
place someone goes specifically to inspect it.

## Dependencies

### Requires
- 017-outlier-exclusion — the exclusions it draws
- 016-daily-rollup-job — the medians it compares
- 025-listing-explorer — where a clicked observation leads

### Enables
- Nothing downstream. Like the rest of unit 005, this is a judgement surface

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Only one source enabled | Agreement view says so plainly; it does not render an empty comparison |
| A printing with two observations | Drawn, with the count prominent; two points are not a distribution and the view should not pretend otherwise |
| Every source disagrees wildly | A real signal — either a thin market or several broken connectors. Both are worth seeing |
| A source's currency differs | Compared after conversion at the day's rate, with the original shown on hover |
| Sealed products | Same view, keyed on the product rather than a printing |

## Out of Scope

- Automatically down-weighting a disagreeing source. `weight` exists on the source row; changing it
  is a human decision informed by this view
- Excluding an individual observation by hand
