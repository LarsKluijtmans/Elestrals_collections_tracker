---
id: 028-coverage-and-match-quality
unit: 005-admin-console
intent: 002-price-intelligence
status: complete
priority: must
created: '2026-08-15T15:00:00Z'
assigned_bolt: 015-admin-analysis
implemented: true
---

# Story: 028-coverage-and-match-quality

## User Story

**As an** admin
**I want** to see how much of the catalog we are actually pricing and how well titles are matching
**So that** I can answer "is this data good enough to show anyone?" with evidence instead of a
feeling

## Acceptance Criteria

- [ ] **Given** the coverage view, **When** it renders, **Then** it shows the proportion of tracked
      printings with an observation in the last 7 days, over time
- [ ] **Given** coverage, **When** it renders, **Then** it separates **all** tracked printings from
      **owned** printings, because the Must-level goal is about owned ones
- [ ] **Given** match quality, **When** it renders, **Then** it shows the accept rate per source and
      per scan mode as a trend
- [ ] **Given** rejections, **When** they are shown, **Then** they are **grouped and counted by
      reason**, so the largest matcher gap is visible without reading rows
- [ ] **Given** a rejection reason group, **When** I open it, **Then** I reach those listings in the
      explorer with the filter already applied
- [ ] **Given** a sustained drop in accept rate, **When** it crosses the threshold, **Then** it is
      visible here and raises an alert through the phase-1 logging path
- [ ] **Given** the unmatched queue, **When** it is summarised, **Then** it distinguishes "no catalog
      card found" from "matched but under the confidence floor" — different problems with different
      fixes

## Technical Notes

This story is the reason unit 005 is scheduled before the user-facing surfaces. Under ADR-004 the
data is scraped, and scraped data has to be *judged* before anything is built on it. This is the
judging.

The last criterion is the most useful thing in the view. "No catalog card found" points at the
catalog — often a real finding, since ADR-001 left the seed incomplete. "Under the floor" points at
the matcher, or at titles that genuinely do not say enough. Merging them into one "unmatched" number
hides which of the two you should be working on.

Grouped rejection reasons follow the phase-1 pattern: an operator should read "83 × graded" rather
than scrolling 83 rows.

Accept rate is trended **per mode**. A deep scan's rate is legitimately lower than a light scan's —
it asks broader questions and gets more unrelated results — and merging them hides both signals.

## Dependencies

### Requires
- 026-run-history-and-health
- 014-observation-store-and-dedupe
- 016-daily-rollup-job — coverage is measured against what actually produced prices

### Enables
- Calibration of story 012's matcher weights, which is the loop this view exists to close

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Catalog is incomplete | Coverage is measured against tracked printings; an incomplete catalog shows high coverage of a small denominator, so the denominator is shown too |
| A source is quarantined | Its accept rate flatlines with no new runs; the view shows the quarantine rather than a mysterious gap |
| Accept rate drops because the market changed | Indistinguishable here from a broken matcher; the drift check (story 010) is what separates them, and both are shown together |
| No owned printings yet | Owned coverage is stated as not applicable rather than 0% |

## Out of Scope

- Fixing anything from this view — it is diagnostic
- Automatic re-calibration of matcher weights
