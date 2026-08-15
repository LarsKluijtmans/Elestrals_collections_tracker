---
id: 006-collection-browse
unit: 004-collection-experience
intent: 001-collection-tracker
type: ddd-construction-bolt
status: planned
stories:
  - 019-collection-table
  - 020-collection-filters
  - 021-saved-views
  - 022-bulk-actions
  - 024-missing-cards-view
  - 036-dashboard
created: 2026-08-09T12:00:00Z
started: null
completed: null
current_stage: null
stages_completed: []

requires_bolts:
  - 005-collection-entry
enables_bolts: []
requires_units: []
blocks: false

complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: 006-collection-browse

## Overview

The collection table with filters, saved views and bulk actions; the missing-cards view; and the
dashboard. This is the bolt where the product becomes something worth showing another person.

## Objective

Ten thousand holdings, browsable at 60fps, filterable along every attribute that matters, with bulk
operations that make selling 200 cards one interaction rather than 200.

## Stories Included

- **019-collection-table**: virtualized table (Must)
- **020-collection-filters**: combining filters, serialised into the URL (Must)
- **021-saved-views**: named presets (Should)
- **022-bulk-actions**: bulk edit, delete, export (Must)
- **024-missing-cards-view**: what I am missing from a set (Must)
- **036-dashboard**: stat tiles, completion rings, recent activity (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [ ] **1. model**: Pending → ddd-01-domain-model.md
- [ ] **2. design**: Pending → ddd-02-technical-design.md
- [ ] **3. implement**: Pending → `frontend/src/pages/{collection,dashboard}/`
- [ ] **4. test**: Pending → ddd-03-test-report.md

## Dependencies

### Requires
- 005-collection-entry (real data to browse)

### Enables
- Nothing in this intent. Intent 002 attaches its value and delta columns to this table.

## Success Criteria

- [ ] 10,000 rows at 60fps on a mid-range laptop; list API p95 < 400ms
- [ ] Cursor pagination, not offset
- [ ] Filters combine, serialise to the URL, and survive reload and the back button
- [ ] Saved view restores filters, sort and density
- [ ] Bulk delete of 500 rows: one confirmation naming the count
- [ ] Partial bulk failure reports which rows failed and applies the rest
- [ ] Missing count and completion agree with the dashboard ring
- [ ] Empty and onboarding states written before the components
- [ ] Full keyboard path, verified with a screen reader; WCAG 2.2 AA
- [ ] Coverage > 80%

## Notes

Build the table with the phase-2 columns in mind but **do not stub them with zeroes**. The dashboard
value tile says "available in phase 2" rather than showing €0 — a zero is a claim, and it is a false
one.

Row height must be fixed per density mode. Variable-height virtualization is the usual cause of
stutter in tables like this, and it is much harder to remove later than to avoid now.
