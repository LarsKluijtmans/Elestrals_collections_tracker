---
id: 015-admin-analysis
unit: 005-admin-console
intent: 002-price-intelligence
type: ddd-construction-bolt
status: complete
stories:
  - 028-coverage-and-match-quality
  - 029-price-distribution-and-source-agreement
created: 2026-08-15T15:25:00Z
started: 2026-08-15T15:30:00Z
completed: 2026-08-15T16:20:00Z
current_stage: done
stages_completed: [model, design, implement, test]

requires_bolts:
  - 014-rollups-and-valuation
enables_bolts: []
requires_units: []
blocks: false

complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 1
  testing_scope: 2
---

# Bolt: 015-admin-analysis

## Overview

The two analysis surfaces: how much of the catalog we are actually pricing and how well titles are
matching, and what the spread of prices behind a median looks like when the sources are compared
against each other.

## Objective

Make "is this data good enough to show anyone?" answerable with evidence. Bolt 013 lets you read
individual listings; this bolt lets you see the shape of all of them at once.

## Stories Included

- **028-coverage-and-match-quality**: is this data good enough to show anyone? (Must)
- **029-price-distribution-and-source-agreement**: do the sources agree, and what did we drop? (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

DDD rather than simple: source agreement needs a defined comparison before it has a UI, and
"systematic offset versus noise" is a modelling question, not a charting one.

## Stages

- [x] **1. model**: Done → ddd-01-domain-model.md
- [x] **2. design**: Done → ddd-02-technical-design.md
- [x] **3. implement**: Done → coverage, accept-rate trends, distribution, agreement views
- [x] **4. test**: Done → ddd-03-test-report.md

## Dependencies

### Requires
- 014-rollups-and-valuation (the medians it compares and the exclusions it draws)

### Enables
- Nothing downstream. Like the rest of unit 005, this is a judgement surface

## Success Criteria

- [ ] Coverage separates **all** tracked printings from **owned** printings, because the Must-level
      goal is about owned ones
- [ ] Accept rate is trended per source **and per mode** — merging deep and light hides both signals
- [ ] Rejections are grouped and counted by reason, and each group links into the explorer with the
      filter applied
- [ ] The unmatched queue distinguishes "no catalog card found" from "matched but under the floor"
- [ ] A sustained accept-rate drop raises an alert through the phase-1 logging path
- [ ] The distribution view draws every observation behind a rollup, with excluded outliers distinct
- [ ] `sold` and `listed` are visually separate in the distribution, never one cloud
- [ ] Where two sources cover a printing, disagreement is quantified; single-source coverage says so
- [ ] Any observation in the distribution links to its `source_url`
- [ ] Coverage > 80%

## Notes

Source agreement is the strongest check available on a scraped pipeline. A connector that is subtly
wrong — parsing the wrong price field, picking up shipping, reading a different currency — produces
plausible numbers that only look wrong next to another source's. Under ADR-004 there is no licensed
reference to check against, so cross-source comparison **is** the reference.

The distinction to design for is systematic offset versus noise: a source 8% high on every printing
is a bug in that connector; a source scattered around the others is a thinner market.

This bolt reads `price_observations` directly rather than rollups — it is the one view whose job is
to explain what the rollup did, so it has to see what the rollup saw.

## Construction result - 2026-08-15

**Status: complete.** Two endpoints and the Quality tab.

Coverage reports the numerator **and** the denominator, because a high ratio over an incomplete
catalog is not the same achievement as a high ratio over a complete one - and ADR-001 left the seed
incomplete, so this is the likely case rather than a hypothetical.

The unmatched queue is split into "no catalog card found" and "matched but under the floor". Those
point at different work - the catalog and the matcher respectively - and merging them into one
"unmatched" number hides which one you should be fixing.

Source agreement compares per-source medians against the cross-source median, on **sold
observations with outliers excluded**. Comparing on asking prices would measure how optimistic each
marketplace's sellers are, which is a different question. With no licensed reference to check
against, this is the only reference the pipeline has.

**Not built:** the "sustained accept-rate drop raises an alert" criterion. The trend is computed
and displayed, and the console colours a falling rate - but nothing pages anyone. That needs the
phase-1 outbox, which has not shipped.
