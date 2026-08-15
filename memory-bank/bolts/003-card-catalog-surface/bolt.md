---
id: 003-card-catalog-surface
unit: 002-card-catalog
intent: 001-collection-tracker
type: ddd-construction-bolt
status: in-progress
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

- ✅ **1. model**: Complete → `ddd-01-domain-model.md`

  No new entities and no new aggregates — this is the read side of bolt 002's context.
  13 value objects (read models), 5 domain services, repository additions only.
  **Human checkpoint — approve before Stage 2.**

- ✅ **2. design**: Complete → `ddd-02-technical-design.md`

  Six ranking tiers, plain indexed SQL over FULLTEXT with a written revisit trigger,
  `/sets` kept anonymous and cacheable, and the keyboard contract bolt 005 will consume.
  Corrects a Stage 1 imprecision: the "Teratlas" example was an infix match, not a word
  prefix — they are now separate tiers. **Human checkpoint — approve before Stage 3/4.**

- ✅ **3. ADR analysis**: Complete → `adr-002-search-implementation.md` (indexed as ADR-002)

- ✅ **4. implement**: Complete → 5 endpoints, 5 services, `core/pagination.py`,
  5 frontend components, 4 pages. `Gate` restructured so the public pages work signed out.

- ⏳ **5. test**: **Partial** → `ddd-03-test-report.md`

  119 backend tests (46 new, 97% on bolt-003 modules) · 12 frontend tests · typecheck clean ·
  build passes. The keyboard contract bolt 005 consumes is pinned.
  **Not met:** the < 150ms p95 target is unmeasurable — no MySQL, and the catalog has no data.
  **Not verified:** MySQL collation/ordering, browser rendering, a full WCAG audit.

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
