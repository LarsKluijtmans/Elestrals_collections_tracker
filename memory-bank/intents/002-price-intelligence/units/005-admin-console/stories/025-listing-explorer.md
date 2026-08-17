---
id: 025-listing-explorer
unit: 005-admin-console
intent: 002-price-intelligence
status: complete
priority: must
created: '2026-08-15T15:00:00Z'
assigned_bolt: 013-admin-console-core
implemented: true
---

# Story: 025-listing-explorer

## User Story

**As an** admin
**I want** to see every listing the harvester holds and why it matched or did not
**So that** I can judge whether this scraped data is good enough before anything is built on it

## Acceptance Criteria

- [ ] **Given** listings exist, **When** I open the explorer, **Then** I see them paged, newest
      first, with title, source, price, status, matched SKU and confidence
- [ ] **Given** the filters, **When** I use them, **Then** I can filter by source, run, scan mode,
      listing status, matched/unmatched, kind and confidence band, and combine them
- [ ] **Given** any listing, **When** I open it, **Then** I see its full match note — the reason it
      matched, or the reason it was refused — and a link to its `source_url`
- [ ] **Given** the unmatched filter, **When** I apply it, **Then** I reach the queue of listings the
      catalog or the matcher is missing in one click from the explorer's default view
- [ ] **Given** 50,000 listings for a source, **When** I page through them, **Then** each page
      returns within 400ms p95
- [ ] **Given** a listing that has ended, **When** I view it, **Then** its status distinguishes
      `ended_sold`, `ended_unsold` and `ended_unknown`, and the UI does not describe
      `ended_unknown` as a sale
- [ ] **Given** any view in the explorer, **When** it renders, **Then** no buyer or seller identity
      appears, because none was ever collected

## Technical Notes

This is the surface the "admin-only raw data" decision exists for. Everything else in the console
supports it.

The unmatched queue deserves the emphasis in the fifth criterion. An unmatched listing is a **lead**
— either a product missing from the catalog (a real finding, and one of the two things a deep scan
is for) or a gap in the matcher. Reading the notes is how those are told apart, and it is the main
feedback loop for improving story 012.

Paging at 50k needs the index on `(source_id, kind, match_confidence)` plus the status/seen index
from the listing table; the confidence-band filter is a range over an indexed column rather than a
computed bucket.

`ended_unknown` must be labelled as what it is — "ended, reason unknown" — and never as "sold". The
whole invariant chain from story 015 is undone if the UI describes it loosely.

## Dependencies

### Requires
- 024-admin-shell-and-routing
- 012-title-to-printing-matcher — the notes it displays
- 014-observation-store-and-dedupe

### Enables
- 028-coverage-and-match-quality — the aggregate view of what this shows row by row

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| No listings at all | An empty state saying no scan has produced listings yet, with a link to trigger one |
| A listing whose matched printing was later removed from the catalog | Shows as unmatched with a note; the FK is `SET NULL` on delete |
| Very long titles | Truncated in the table, full in the detail |
| Filter combination returning nothing | "No listings match these filters", distinct from "no listings exist" |
| A source deleted from config | Its listings remain and are filterable; history is not erased by config |

## Out of Scope

- Editing or correcting a match — Checkpoint 1 scoped it out
- Export — same
