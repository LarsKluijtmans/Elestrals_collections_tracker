---
unit: 003-matching-and-observations
intent: 002-price-intelligence
phase: inception
status: complete
created: '2026-08-15T14:55:00Z'
updated: '2026-08-15T14:55:00Z'
---

# Unit Brief: matching-and-observations

## Purpose

Turn a seller's sentence into a fact about a specific SKU, or refuse to. A listing titled

> Elestrals Vipyro FE01 012/126 Holo 1st Edition NM

has to become a `printing_id`, a condition and a confidence — or become a recorded rejection with a
reason. This unit is the accuracy ceiling of everything downstream: a foil price recorded against
the non-foil printing moves a median that somebody's collection valuation is computed from, and
nothing later in the pipeline can detect it.

The design commitment is that the matcher **refuses rather than guesses**. A matcher that places 95%
of titles is worse than one that places 60%, if the extra 35% are wrong.

## Scope

### In Scope
- Title → printing / sealed product, with a confidence score
- Explicit refusals: graded slabs, multi-card lots, proxies and customs, and any language with no
  matching printing
- Condition extraction from title text
- `price_observations`: append-only, deduped, fully provenanced
- The `sold` / `listed` split, enforced against source configuration
- Keeping rejected listings as **leads**, with the reason attached

### Out of Scope
- Fetching anything (unit 002)
- Aggregating anything (unit 004)
- Manually correcting a wrong match — deliberately deferred; it needs the explorer from unit 005
  to exist first, and it was scoped out at Checkpoint 1

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-3 | Match a sale to a printing | Must |
| FR-4 | Sold versus listed | Must |

---

## Domain Concepts

### Key Entities
| Entity | Description | Attributes |
|--------|-------------|------------|
| Match | What the matcher concluded, and why | `kind`, `printing_id`, `sealed_product_id`, `condition`, `confidence`, `note` |
| PriceObservation | One price point, append-only | `source_id`, `run_id`, `printing_id`, `sealed_product_id`, `condition`, `sale_type`, `observed_at`, `price_cents`, `currency`, `external_id`, `source_url`, `match_confidence` |
| CatalogIndex | The catalog in memory, built once per run | printings, sealed products, sets |

### Key Operations
| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `match(title)` | Title → SKU, or a refusal with a reason | title, kind hint | `Match` |
| `record_observation()` | Insert one price point, or do nothing | observation values | written / already had it |
| `clears(floor)` | Placed **and** confident — both, or nothing is written | match, floor | bool |

### Refusal rules

| Refused | Because |
|---|---|
| Graded slab (`PSA 10`, `BGS 9.5`, `slabbed`) | A different market from a raw card, and the schema has nowhere to record a grade. A slab price in a raw median inflates every valuation containing that card |
| Multi-card lot (`3x`, `playset`, `bulk`) | "3x Vipyro at $30" is not a $30 Vipyro. Dividing by a quantity parsed out of a title is arithmetic on a guess |
| Proxy / custom / replica | It is not the card |
| A language with no matching printing | An English printing is not a cheaper version of a Japanese card; it is a different card |
| Anything under the confidence floor | FR-3: rejected, not stored as a low-confidence fact |

A refusal is not data loss. The listing stays in `market_listings` with the reason in `match_note`,
because an unmatched listing is a lead — either a product missing from the catalog or a gap in the
matcher, and those are told apart by reading the notes.

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 4 |
| Must Have | 4 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 012-title-to-printing-matcher | Refuse rather than guess | Must | Planned |
| 013-condition-extraction | Read the condition off the title | Must | Planned |
| 014-observation-store-and-dedupe | Append-only, and free to re-run | Must | Planned |
| 015-sold-vs-listed-separation | A sale is a sale; an asking price is not | Must | Planned |

---

## Dependencies

### Depends On
| Unit | Reason |
|------|--------|
| 002-scrapers | There is nothing to match until there are listings |
| intent 001 / 002-card-catalog | `printings` is what a title is matched *to*; an empty catalog matches nothing |

### Depended By
| Unit | Reason |
|------|--------|
| 004 | Rollups aggregate these observations |
| 005 | The explorer's most useful filter is "what could not be matched" |

### External Dependencies
None. This unit is pure computation over data units 002 and intent 001 already fetched — which is
why it can be tested exhaustively without a network.

---

## Technical Context

### Suggested Technology
A catalog index built once per run and held in memory (a few MB at 50k printings), bucketed by first
word so matching a title tests a handful of names rather than all of them. Deterministic scoring
with named weights — every weight a constant, so the calibration can be tuned against the
accept-rate trend the console shows. `Decimal` for money; never `float`.

### Integration Points
| Integration | Type | Protocol |
|-------------|------|----------|
| `elestrals` catalog | inbound read | MySQL cross-schema, read-only |

### Data Storage
| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| `price_observations` | SQL | 50M at 12 months | permanent, append-only |

---

## Constraints

- **`UNIQUE (source_id, external_id)` is what makes a re-run free.** A `sold` row keys on the
  source's transaction id; a `listed` row keys per listing per day, so an hourly light scan writes
  one asking-price point a day and tomorrow's change still lands as its own row.
- **Append-only.** A correction is a new row plus an exclusion flag, never an edit. A price history
  that can be silently rewritten is not evidence.
- **`sold` requires a source configured to report sales**, checked against `price_sources`, not
  against the connector's claim. A wrong connector must not be able to manufacture a sale.
- **Every observation keeps its `source_url`.** Under ADR-004 this matters more, not less: scraped
  data that cannot be traced to a page a human can open is not evidence of anything.
- The confidence floor is configuration, not a constant, because it will be re-calibrated once the
  console shows what the real distribution looks like.
