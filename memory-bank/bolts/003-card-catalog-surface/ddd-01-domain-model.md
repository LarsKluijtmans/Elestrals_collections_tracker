---
unit: 002-card-catalog
bolt: 003-card-catalog-surface
stage: model
status: complete
updated: 2026-08-10T14:45:00Z
---

# Static Model - Card Catalog Surface

Covers stories `010-card-search`, `011-set-browser`, `012-card-detail`,
`034-admin-catalog-console`.

## Bounded Context

**Same context as bolt 002, opposite side.** Bolt 002 owns how the catalog is *written*; this
bolt owns how it is *read*. No new persistent entity is introduced — `Set`, `Card`, `Printing`,
`CatalogImport` and `ImportRejection` already exist and are unchanged.

What is new is a set of **read models**: shapes assembled for a screen, which deliberately do
not mirror the write model. `CardSearchResult` is not a `Card`; it is what a search row needs
and nothing more.

The context boundary that shapes almost every decision below:

> **Public catalog reads must never vary on a user.** (`standards/api-conventions.md`)

`/cards`, `/sets` and `/cards/{id}` serve signed out and are cacheable. Anything user-specific —
owned counts, completion rings, wishlist state — cannot ride along in those responses. It is
fetched separately and merged in the client. This is why set completion, though it appears on
`/sets`, is **not** part of `SetSummary`.

## Domain Entities

No new entities. This bolt reads the ones bolt 002 defined:

| Entity | Read as | Notes |
|---|---|---|
| `Set` | `SetSummary`, `SetChecklist` | `card_count` remains the declared printed size |
| `Card` | `CardSearchResult`, `CardDetail` | the name level |
| `Printing` | `PrintingView` | still the SKU; every selection resolves to one |
| `CatalogImport` | `SourceHealth` | latest run per source drives staleness |
| `ImportRejection` | `RejectionRollup` | grouped by reason for the console |

## Value Objects

| Value Object | Properties | Constraints |
|---|---|---|
| **SearchQuery** | `term`, `set_codes[]`, `elements[]`, `card_types[]`, `rarities[]`, `limit`, `cursor` | `term` trimmed; a query shorter than 2 characters returns empty rather than scanning the catalog. Repeated params OR within an attribute, AND across attributes — the filter algebra in `api-conventions.md`, so URL-serialised UI filters and the API cannot drift |
| **MatchKind** | `exact_name` \| `name_prefix` \| `word_prefix` \| `collector_number` \| `set_code` | The ranking tiers, in order. A closed set so ordering is total and testable |
| **RankedMatch** | `card_id`, `match_kind`, `tiebreak` | Ordering is `(match_kind, tiebreak)`; `tiebreak` is `(set.released_on desc, collector_number asc)` |
| **CardSearchResult** | `card_id`, `name`, `set_code`, `collector_number`, `card_type`, `element`, `primary_printing`, `printing_count`, `image_url`, `alt_text` | A **stable, deterministic** row. Bolt 005's fast-add selects one of these with `Enter`, so identity and order must not wobble between identical queries |
| **PrintingView** | `printing_id`, `rarity`, `finish`, `language`, `edition`, `image_url`, `alt_text` | `printing_id` is what every downstream feature stores |
| **SetSummary** | `code`, `name`, `series`, `released_on`, `card_count`, `imported_count` | User-agnostic by construction. **No completion field** — see the context note |
| **SetChecklistEntry** | `collector_number`, `card_id`, `name`, `printings[]` | Ordered by `collector_number`, gaps included so a missing card is visible |
| **CardDetail** | card fields + `printings[]` + `set` | Every printing of the card, never a filtered subset |
| **AltText** | rendered string | Always `"{name} — {set} {rarity}"`. A WCAG 2.2 AA criterion, so it is generated in one place rather than assembled per component |
| **Staleness** | `last_success_at`, `age_hours`, `state` | `state` ∈ `fresh` \| `ageing` \| `stale` \| `never_run`. Thresholds are configuration, not a magic number in a template |
| **SourceHealth** | `source`, `last_run`, `staleness`, `last_status`, `consecutive_failures` | One row per registered source, including sources that have never run |
| **RejectionRollup** | `reason_code`, `count`, `latest_example` | Grouped so an operator sees "83 × unknown_rarity", not 83 rows |
| **CatalogHealth** | `sources[]`, `sets_below_coverage[]`, `total_rejections_last_run` | The console's whole payload in one shape |

## Aggregates

**None introduced.** Read models are projections, not aggregates: they have no invariants to
protect because they are never written. Inventing an aggregate root here would add a boundary
that guards nothing.

The write-side aggregates from bolt 002 (`Card`, `CatalogImport`) remain the only place catalog
state changes, and nothing in this bolt writes.

## Domain Events

**None emitted.** This bolt is read-only; a query that produced a domain event would be lying
about what it did.

It *consumes* one: `SetCoverageIncomplete`, raised by bolt 002's importer, is what
`sets_below_coverage` surfaces on the console. Bolt 002 deliberately put coverage on the
run-detail response so this bolt reads existing numbers rather than recomputing them.

## Domain Services

| Service | Operations | Dependencies |
|---|---|---|
| **CardSearchService** | `search(SearchQuery) -> list[CardSearchResult]` | CardRepository. Owns the ranking rule: tier by `MatchKind`, then by tiebreak. Deterministic and total-ordered — see the invariant below |
| **SetBrowseService** | `list_sets()`, `checklist(set_code)` | SetRepository, CardRepository. Orders checklists by collector number **including gaps**, so an incomplete import is visible on the page rather than looking like a short set |
| **CardDetailService** | `detail(card_id)` | CardRepository, PrintingRepository. Returns every printing, never a filtered view |
| **CatalogHealthService** | `health()` | CatalogImportRepository, SetRepository. Latest run per source, staleness classification, rejection rollup, sets below declared coverage |
| **AltTextService** | `for_printing(...)`, `for_card(...)` | none — pure. One implementation so the WCAG string cannot drift between the search row, the checklist and the detail page |

### The invariant that shapes the search API

> **Identical queries return identical results in identical order.**

Bolt 005's fast-add flow selects a result with `Enter` after arrow-key navigation. If ordering
were unstable — ties broken by a non-deterministic sort, or by a database's natural row order —
the row under the cursor could change between render and keypress, and a collector would add
the wrong printing to their collection without any error being raised anywhere.

So the sort key is total: `(match_kind, released_on desc, collector_number asc, card_id asc)`.
The final `card_id` term exists only to break exact ties, and it is what makes the order total
rather than merely usually-stable.

This is a domain rule, not a UI detail, because the wrong-card-added failure is silent.

## Repository Interfaces

Additions to the bolt-002 repositories; no new repository classes.

| Repository | Entity | New methods |
|---|---|---|
| **CardRepository** | Card | `search(SearchQuery) -> list[RankedMatch]`, `detail(card_id) -> Card \| None`, `hydrate(card_ids) -> list[Card]` |
| **SetRepository** | Set | `summaries() -> list[SetSummary]` (with imported counts in one query, not N+1) |
| **PrintingRepository** | Printing | `list_for_cards(card_ids) -> dict[card_id, list[Printing]]` — batched, so a 50-row search page is two queries rather than fifty-one |
| **CatalogImportRepository** | CatalogImport | `latest_per_source() -> list[CatalogImport]`, `rejection_rollup(run_id) -> list[RejectionRollup]` |

## Ubiquitous Language

| Term | Definition |
|---|---|
| **Ranked result** | A search row placed by match tier, then by a total tiebreak. Never "relevance" as an opaque score |
| **Match kind** | *Why* a card matched — exact name, name prefix, word prefix, collector number, set code. Determines rank and is worth showing |
| **Checklist** | Every collector number in a set, in order, **including the ones we have not imported**. A checklist that hides gaps is a lie about completeness |
| **Coverage** | Imported cards against `sets.card_count` (bolt 002). Belongs to the catalog |
| **Completion** | How much of a set a *user* owns (bolt 004). Belongs to a person. Coverage and completion are different words on purpose — conflating them is how "you own 100%" appears for a set we only half-imported |
| **Staleness** | How long since a source last imported successfully. `never_run` is a first-class state, not null |
| **Primary printing** | The printing shown on a search row when a card has several — lowest rarity tier, so the row reads as the common version |
| **Alt text** | `"{name} — {set} {rarity}"`, generated centrally. A WCAG 2.2 AA requirement |

## Story coverage

| Story | Covered by |
|---|---|
| `010-card-search` | SearchQuery, MatchKind, RankedMatch, CardSearchResult, CardSearchService, total-order invariant |
| `011-set-browser` | SetSummary, SetChecklistEntry, SetBrowseService, gaps-included ordering |
| `012-card-detail` | CardDetail, PrintingView, CardDetailService, AltText |
| `034-admin-catalog-console` | SourceHealth, Staleness, RejectionRollup, CatalogHealth, CatalogHealthService |

## Open questions for Stage 2

1. **Search implementation.** MySQL `LIKE 'term%'` on the indexed `cards.name` covers name-prefix
   cheaply, but word-prefix ("atlas" matching "Teratlas") needs either a FULLTEXT index or a
   generated normalised column. FULLTEXT changes the ranking story materially. Decide against the
   <150ms p95 target with a full catalog.
2. **Completion ring hydration.** The bolt notes say build the ring with a null state. Confirm the
   split: `/sets` anonymous and cacheable, completion fetched from bolt 004's `/api/v1/completion`
   and merged client-side. Anything else breaks the never-vary-on-user rule.
3. **Primary-printing choice.** Lowest rarity tier is proposed. A card whose only printing is
   `secret` should still show something, so the rule needs a defined fallback rather than an
   assumption that a common printing exists.
