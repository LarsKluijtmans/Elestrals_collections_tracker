---
id: 012-matching-and-observations
unit: 003-matching-and-observations
intent: 002-price-intelligence
type: ddd-construction-bolt
status: complete
stories:
  - 012-title-to-printing-matcher
  - 013-condition-extraction
  - 014-observation-store-and-dedupe
  - 015-sold-vs-listed-separation
created: 2026-08-15T15:25:00Z
started: 2026-08-15T15:30:00Z
completed: 2026-08-15T16:20:00Z
current_stage: done
stages_completed: [model, design, implement, test]

requires_bolts:
  - 011-scraper-connectors
enables_bolts:
  - 013-admin-console-core
requires_units: []
blocks: false

complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 1
  testing_scope: 3
---

# Bolt: 012-matching-and-observations

## Overview

Turn a seller's sentence into a fact about a specific SKU — or refuse to, and say why. Then store
that fact append-only, deduped, and traceable to the page it came from.

## Objective

Set the accuracy ceiling for everything downstream. A foil price recorded against the non-foil
printing moves a median that somebody's collection valuation is computed from, and nothing later in
the pipeline can detect it.

## Stories Included

- **012-title-to-printing-matcher**: refuse rather than guess (Must)
- **013-condition-extraction**: read the condition off the title (Must)
- **014-observation-store-and-dedupe**: append-only, and free to re-run (Must)
- **015-sold-vs-listed-separation**: a sale is a sale; an asking price is not (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. model**: Done → ddd-01-domain-model.md
- [x] **2. design**: Done → ddd-02-technical-design.md
- [x] **3. implement**: Done → matcher, `price_observations` migration, the sale-type guard
- [x] **4. test**: Done → ddd-03-test-report.md, **one test per refusal rule**

## Dependencies

### Requires
- 011-scraper-connectors (listings to match)
- 002-card-catalog-schema-import (the printings to match *to*)

### Enables
- 013-admin-console-core
- 014-rollups-and-valuation

## Success Criteria

- [ ] A fully specified title resolves to exactly one printing above the floor
- [ ] The longer of two overlapping card names wins, and no false ambiguity is reported
- [ ] Graded slabs, multi-card lots and proxies are each refused, with the reason recorded
- [ ] A language with no matching printing is refused, never folded onto English
- [ ] An underspecified title falls **under** the floor rather than guessing a printing
- [ ] Every refusal still stores the listing, with its reason, as a lead
- [ ] Re-running a scan the same day writes no new observations
- [ ] A price change tomorrow lands as its own row
- [ ] A source not configured to report sales **cannot** produce a `sold` observation, even when its
      connector claims one
- [ ] Every observation carries a `source_url` that leads to a page a human can open
- [ ] Coverage > 80%

## Notes

The interesting half of the test suite is the **rejections**. A matcher placing 95% of titles is
worse than one placing 60% if the extra 35% are wrong, because a wrong SKU is undetectable
downstream. Each refusal rule gets its own test naming the failure it prevents.

Two implementation traps worth writing down now:

- The collector number must be read from the **raw** title. Normalising the string strips the
  punctuation (`012/126`, `#012`) that the number is made of.
- Card names need bucketing by first word, or matching one title tests all 50,000 names.

`_ended_status` and the sale-type guard are the same invariant expressed twice — a disappearance is
not a sale, and a connector cannot override its source's configuration. Both checks belong at the
last moment before the write, where a wrong connector, a wrong config row and a wrong test double
all have to pass through them.

## Construction result - 2026-08-15

**Status: complete.** The matcher ported from the earlier single-backend prototype, with its
vocabulary copied into this service rather than imported across a boundary that no longer exists.

Every refusal rule has a test naming the failure it prevents:

| Refusal | Test |
|---|---|
| Graded slab | `test_a_graded_slab_is_refused` - a PSA 10 and a raw copy are two markets |
| Multi-card lot | `test_a_multi_card_lot_is_refused` - dividing by a title-parsed quantity is arithmetic on a guess |
| Proxy / custom | `test_a_proxy_is_refused` |
| Language with no printing | `test_a_language_with_no_printing_is_refused_rather_than_folded_onto_english` |
| Under the floor | `test_an_underspecified_title_falls_under_the_floor` |

Idempotency holds on both keys: `test_a_second_deep_scan_over_unchanged_results_writes_nothing_new`
asserts zero new listings and zero new observations.

**The sold guard is enforced at the last moment before the write**, against
`price_sources.reports_sold` rather than the connector's claim -
`test_a_source_that_does_not_report_sales_cannot_end_a_listing_as_sold`, and its positive twin.

**Departure from the plan:** `printing_id` and `sealed_product_id` are plain columns, not foreign
keys. They point into `elestrals`, which this service cannot write and does not own; a cross-schema
FK would make phase 1 unable to change its own catalog without this service's cooperation. The cost
is a dangling id when a printing is deleted, which the explorer shows as unmatched - the honest
reading of "the catalog no longer has this".
