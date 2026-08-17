---
id: 033-slice-valuation
unit: 006-price-surfaces
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 016-price-surfaces
implemented: false
---

# Story: 033-slice-valuation

## User Story

**As a** collector
**I want** to value any filtered part of my collection
**So that** I can answer "what is my Base Set worth?" or "what are my foils worth?" without doing
arithmetic myself

## Acceptance Criteria

- [ ] **Given** `/portfolio/slice`, **When** I apply filters, **Then** they are the **same filters**
      as `/collection`, behaving identically
- [ ] **Given** a slice, **When** it is valued, **Then** it states its own coverage and confidence,
      not the whole collection's
- [ ] **Given** a slice with unpriced items, **When** it renders, **Then** they are excluded and
      counted, as everywhere else
- [ ] **Given** a slice of 5,000 holdings, **When** it is valued, **Then** it returns within 1.5s p95
- [ ] **Given** a filter combination matching nothing, **When** it is valued, **Then** it says no
      items match, distinct from a value of zero

## Technical Notes

Reusing `/collection`'s filter implementation rather than writing a parallel one is the whole design
decision here. Two filter implementations for the same data model will disagree, and the
disagreement will surface as a valuation that does not match the item list the user is looking at —
which reads as the valuation being broken.

Saved views from phase 1 should be valuable directly, since they are already a filter definition.

## Dependencies

### Requires
- 020-collection-valuation
- 032-portfolio-page — shares its components
- intent 001 / 004-collection-experience — the filters and saved views

### Enables
- Nothing downstream

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Slice is the whole collection | Same number as `/portfolio` — and if it is not, one of the two is wrong, which is worth a test |
| Slice contains only unpriced items | Value unavailable with coverage 0 of N |
| A saved view referencing a removed set | Behaves as `/collection` does with the same view |
| Very narrow slice, one card | Valued with its observation count and confidence, as everywhere |

## Out of Scope

- Historical value of a slice — snapshots are collection-level (story 022)
- Exporting a valuation
