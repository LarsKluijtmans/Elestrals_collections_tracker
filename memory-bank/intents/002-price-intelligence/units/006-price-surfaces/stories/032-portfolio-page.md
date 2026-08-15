---
id: 032-portfolio-page
unit: 006-price-surfaces
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 016-price-surfaces
implemented: false
---

# Story: 032-portfolio-page

## User Story

**As a** collector
**I want** one page that tells me what my collection is worth and how that has changed
**So that** the tracking I have been doing turns into something I can actually read

## Acceptance Criteria

- [ ] **Given** `/portfolio`, **When** it loads, **Then** it shows current value, coverage
      ("412 of 500 items valued") and overall confidence
- [ ] **Given** the page, **When** it renders, **Then** value over time is drawn from
      `collection_snapshots`
- [ ] **Given** holdings with a cost basis, **When** P/L is shown, **Then** the covered proportion is
      stated alongside it
- [ ] **Given** the page, **When** it renders, **Then** best and worst performers are listed with
      their contribution and observation counts
- [ ] **Given** unpriced holdings, **When** the page renders, **Then** they are shown as a count with
      a way to see which ones — never folded into the total as zero
- [ ] **Given** the dashboard value tile from phase 1, **When** this ships, **Then** it shows a real
      number instead of "available in phase 2"
- [ ] **Given** the collection table from phase 1, **When** this ships, **Then** it gains value and
      delta columns

## Technical Notes

The unpriced count needs to be a **link**, not just a number. "88 items could not be valued" is
informative; being able to see which 88 is actionable, and it is often the same feedback loop the
admin console has — an unpriced item is usually a printing nothing has been seen selling.

Coverage and confidence are not footnotes here. They are the difference between a number a collector
can rely on and one they will quietly stop believing the first time it looks wrong.

## Dependencies

### Requires
- 021-portfolio-history-and-pl
- intent 001 / 004-collection-experience — the collection table these columns attach to

### Enables
- 033-slice-valuation reuses this page's components

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| New user with no holdings | Empty state pointing at adding a collection, not a €0 portfolio |
| Collection entirely unpriced | Value unavailable with coverage 0 of N, and the unpriced list front and centre |
| History shorter than the selected range | Chart starts where the data starts |
| A very large collection | Values from the nightly snapshot rather than computed live where possible |

## Out of Scope

- Filters (story 033)
- Alerts (unit 007)
