---
id: 003-card-catalog-surface
unit: 002-card-catalog
intent: 001-collection-tracker
type: ddd-construction-bolt
status: planned
stories:
  - 010-card-search
  - 011-set-browser
  - 012-card-detail
  - 034-admin-catalog-console
created: 2026-08-09T12:00:00Z
started: null
completed: null
current_stage: null
stages_completed: []

requires_bolts:
  - 002-card-catalog-schema-import
enables_bolts:
  - 005-collection-entry
requires_units: []
blocks: false

complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 1
  testing_scope: 2
---

# Bolt: 003-card-catalog-surface

## Overview

Make the catalog visible and searchable: ranked search, the set gallery and checklist, card detail,
and the operator console over import health.

## Objective

A visitor — signed in or not — can find any card, browse any set, and see every printing of a card.
An operator can see whether the catalog is healthy.

## Stories Included

- **010-card-search**: ranked prefix search (Must)
- **011-set-browser**: `/sets` and `/sets/:code` (Must)
- **012-card-detail**: `/cards/:id` with every printing (Must)
- **034-admin-catalog-console**: `/admin/catalog` (Should)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [ ] **1. model**: Pending → ddd-01-domain-model.md
- [ ] **2. design**: Pending → ddd-02-technical-design.md
- [ ] **3. implement**: Pending → `backend/app/controllers/catalog.py`, `frontend/src/pages/`
- [ ] **4. test**: Pending → ddd-03-test-report.md

## Dependencies

### Requires
- 002-card-catalog-schema-import (there must be a catalog)

### Enables
- 005-collection-entry (the add flow is built on this search)

## Success Criteria

- [ ] 3-character prefix returns ranked results in < 150ms p95
- [ ] Results keyboard-navigable and selectable with `Enter` — the add flow depends on this contract
- [ ] Card detail lists every printing with rarity as a material and element as a named tinted chip
- [ ] `/admin/catalog` shows runs, staleness and rejections; non-operator gets 403
- [ ] All three public pages work signed out
- [ ] WCAG 2.2 AA, including alt text `"{name} — {set} {rarity}"`
- [ ] Coverage > 80%

## Notes

The search contract established here — ranked results, arrow-navigable, `Enter` selects — is
consumed directly by bolt 005's fast-add flow. Design it as an API for that flow, not only as a
page, or it will need reworking two bolts later.

Completion rings appear on `/sets` only when signed in, and they depend on bolt 004. Build the ring
component here with a null state so the page is complete either way.
