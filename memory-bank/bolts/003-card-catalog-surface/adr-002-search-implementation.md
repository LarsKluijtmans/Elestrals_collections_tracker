---
adr: 002
title: Card search — tiered SQL scan, not FULLTEXT
status: accepted
date: 2026-08-10
bolt: 003-card-catalog-surface
stage: 2-design
---

# ADR-002: Card search implementation

## Context

Story `010-card-search` requires ranked prefix search returning in **< 150ms p95** with the full
catalog loaded. `ddd-01-domain-model.md` requires the ranking to be explicit and total: six
ordered `MatchKind` tiers, then `(released_on desc, collector_number asc, card_id asc)`.

That totality is not cosmetic. Bolt 005's fast-add navigates results with arrow keys and commits
with `Enter`; if ordering wobbled between renders, the row under the cursor could change between
render and keypress and a collector would add the wrong printing with **no error raised
anywhere**. Whatever backs search has to produce a stable, explainable order.

The catalog's size is the other governing fact. `unit-brief.md` puts it at roughly **5,000 cards
and 50,000 printings** — and only cards are searched.

## Decision

**Query `cards` directly with a `CASE` expression that assigns the tier, ordered by that tier
then the tiebreak.** No FULLTEXT index, no denormalised token table, no search engine.

Tiers 1, 2 and 4 are index-assisted (`ix_cards_name`, `uq_cards_set_number`). Tiers 3 and 6 are
scans, which at ~5,000 rows MySQL completes in single-digit milliseconds — roughly two orders of
magnitude inside the budget.

A term shorter than two characters returns an empty page without querying at all.

## Alternatives considered

**1. MySQL FULLTEXT with boolean-mode prefix (`term*`).**
Rejected. Three concrete problems, not stylistic ones:

- `innodb_ft_min_token_size` defaults to **3**, so two-character searches return nothing —
  silently, and exactly in the search-as-you-type window where a collector is still typing.
- Stopword lists would drop legitimate short card names.
- `MATCH ... AGAINST` produces a relevance score that would compete with the explicit tier
  ordering the domain requires. We would rank twice and have to explain the disagreement, or
  discard the score and pay for an index we ignore.

**2. A `card_search_terms` projection table** (one row per card per searchable token, indexed on
the token).
Rejected *for now*, and it is the natural successor. It gives exact tier control with an indexed
prefix scan on every tier. The cost is freshness: the table has to be maintained by the importer,
which either couples bolt 002's upsert to a bolt-003 projection, or leaves a table that can drift
out of step with the catalog it describes. That is a real correctness liability bought to solve a
performance problem we do not have.

**3. An external search engine** (OpenSearch, Meilisearch, Typesense).
Rejected. A new service, a new deployment, a new failure mode and a new sync problem, for 5,000
rows. Phase 2 adds Celery and Redis; adding a search cluster on top of that for a dataset that
fits comfortably in memory would be infrastructure as decoration.

## Consequences

**Good**

- Zero new infrastructure, zero new schema, zero new sync path. Search cannot go stale, because
  it reads the catalog rather than a copy of it.
- The tier is a `CASE` expression, so ranking is readable in the query and assertable in a test.
  `match_kind` is returned on the wire, letting tests assert *why* a row ranked where it did
  rather than pinning an opaque position.
- Two-character searches work, which the FULLTEXT route would have broken by default.

**Bad**

- Tiers 3 and 6 scan. This is fine at 5,000 rows and would not be at 500,000.
- Accent- and case-folding depend on the column collation (`utf8mb4_unicode_ci`) rather than an
  analyzer we control. Adequate for card names today; a genuinely multilingual catalog would want
  more.
- No typo tolerance. "Teratals" finds nothing. Acceptable for a catalog people search by names
  they are reading off a card in their hand.

**Revisit trigger — written down so it is a measurement, not a judgement call**

Move to alternative 2 when **either**:

- measured search p95 exceeds **100ms** (two thirds of the budget, leaving room to act), or
- the catalog passes **100,000 cards**.

Because `MatchKind` is a domain concept rather than a storage detail, that migration changes the
query layer only: no API change, no response-shape change, and the ordering tests carry over
unmodified. That property is the main reason this decision is cheap to reverse, and it is why
taking the simple option now is not a debt.
