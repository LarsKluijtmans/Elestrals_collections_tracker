---
unit: 002-card-catalog
bolt: 002-card-catalog-schema-import
stage: model
status: complete
updated: 2026-08-10T13:10:00Z
---

# Static Model - Card Catalog

Covers stories `007-catalog-schema`, `008-catalog-importer`, `009-import-run-reporting`.

Source of truth for this bolt is the **curated CSV seed** — see `adr-001-catalog-data-source.md`.
The model below is deliberately source-agnostic: the seed enters through the same `SourceAdapter`
port a licensed API would, so the ADR's decision touches one adapter and no domain rule.

## Bounded Context

**The Card Catalog is the canonical record of what exists — never of who owns it.**

It is globally shared, read-mostly, and upstream of every other context in the product. Inventory,
completion, valuation and listings are all queries that resolve *through* it. Nothing in this
context knows a user exists; the importer sends no user data outbound and reads no user table.

| Concern | In this context | Elsewhere |
|---|---|---|
| What cards exist, in what physical variants | ✅ `printings` | |
| Who owns a copy, and in what condition | | unit 003 `inventory_items` |
| What a copy is worth | | intent 002 `price_observations` |
| Whether a copy is for sale | | intent 003 `listings` |
| Whether a SKU is *worth pricing* | ✅ `is_tracked_for_price` | consumed by intent 002 |

The context boundary is the reason `is_tracked_for_price` lives here and price *values* do not: the
catalog decides what is worth watching, the pricing context decides what it is worth.

## Domain Entities

| Entity | Properties | Business Rules |
|---|---|---|
| **Set** | `code`, `name`, `series`, `released_on`, `card_count`, `logo_asset_url` | `code` globally unique. **`card_count` is the *printed* set size, never the number of rows imported** — deriving it from the import makes an incomplete catalog report 100% completion, a wrong answer that looks right. Set may exist with zero cards (declared before seeded). |
| **Card** | `set_id`, `collector_number`, `name`, `card_type`, `element`, `rune_type`, `subtype`, `attack`, `defence`, `spirit_cost`, `rules_text`, `flavour_text`, `artist` | `(set_id, collector_number)` unique. `element` required for `elestral`/`spirit`, normally NULL for `rune`; `rune_type` required for `rune` and NULL otherwise; `attack`/`defence` only for `elestral`. A Card belongs to exactly one Set and cannot move between Sets. |
| **Printing** | `card_id`, `rarity`, `finish`, `language`, `edition`, `image_url`, `is_tracked_for_price` | **This is the SKU.** `(card_id, rarity, finish, language, edition)` unique. Every Card has ≥ 1 Printing — a Card with none is a normalisation bug, not a valid state. `image_url` stores a URL, never bytes, until written permission exists. |
| **SealedProduct** | `set_id`, `kind`, `name`, `contents_note`, `image_url`, `is_tracked_for_price` | The *product*, never anyone's inventory. `set_id` NULL is legal for cross-set bundles. |
| **CatalogImport** | `source`, `started_at`, `finished_at`, `status`, `sets_seen`, counts, `error_summary` | Status lifecycle is `running → success \| partial \| failed`, one direction only. `finished_at` is set **iff** status is terminal. A run that fails mid-source is `partial`, and the catalog it wrote must still be internally consistent. |
| **ImportRejection** | `import_id`, `source_ref`, `raw_record`, `reason_code`, `field`, `message` | Exists so a rejection is *reportable*, not merely logged. Immutable once written. Always belongs to exactly one CatalogImport. |

## Value Objects

| Value Object | Properties | Constraints |
|---|---|---|
| **PrintingKey** | `set_code`, `collector_number`, `rarity`, `finish`, `language`, `edition` | **The natural key, and the whole basis of idempotency.** Equality by value. Stable across runs and across sources — two sources describing the same physical card must produce an equal key or the catalog doubles. |
| **Rarity** | one of `common`, `uncommon`, `rare`, `holo_rare`, `full_art`, `alt_art`, `prismatic`, `secret`, `promo` | Closed set. An unmapped source value is a **rejection**, never a silent `common`. |
| **Finish** | one of `normal`, `foil`, `reverse_foil`, `prismatic` | Closed set. Orthogonal to Rarity — `prismatic` appears in both and they are not interchangeable. |
| **Edition** | one of `unlimited`, `first` | Sets in the `FE` series default to `first`; everything else to `unlimited`. A default is applied by the adapter, never guessed by the normaliser. |
| **LanguageTag** | BCP-47, default `en` | `CHAR(5)`. Only `en` is seeded in phase 1; the column exists so a later language is an insert, not a migration. |
| **SpiritCost** | map of element → count | Non-negative counts, empty map allowed. Elestrals and some Runes only. |
| **CanonicalCard** | a Set ref, Card fields, and ≥ 1 Printing | The normaliser's success output. Complete or non-existent — see the whole-record rule under Aggregates. |
| **Rejection** | `reason_code`, `field`, `message`, `raw_record` | The normaliser's failure output. Carries the raw record so an operator can see what arrived, not just that something failed. |
| **ContentFingerprint** | stable hash over a Card's or Printing's meaningful fields | Excludes `id`, `created_at`, `updated_at`. Exists to make "unchanged" **detectable** — see the invariant below. |
| **ImportCounts** | `sets_seen`, `cards_added`, `cards_updated`, `cards_unchanged`, `printings_added`, `rejected` | Monotonic within a run. `unchanged` is tracked explicitly because it is the success signal for a re-run, not the absence of one. |

## Aggregates

| Aggregate Root | Members | Invariants |
|---|---|---|
| **Card** | its Printings | A Card is written **whole or not at all** — Card plus all its Printings commit in one transaction. A partially-written card is the failure mode this bolt exists to prevent. Printings are unique on `(rarity, finish, language, edition)`. Deleting a Card deletes its Printings; a Printing has no independent life. |
| **Set** | — (references Cards by id) | Kept deliberately small. Cards are *not* members: an aggregate holding ~50k Printings could never be loaded to enforce anything, and Set's only real invariant — `card_count` is the printed size — needs no Card to enforce. Cross-aggregate consistency (coverage) is a **report**, not an invariant. |
| **SealedProduct** | — | Independent. Never references inventory. |
| **CatalogImport** | its ImportRejections | Counts and rejections belong to exactly one run and are append-only. Terminal status freezes the aggregate: nothing may be added after `finished_at` is set. |

### The invariant that shapes the implementation

> **A second run over unchanged sources performs zero writes.**

This is a bolt success criterion, and it does not come free from `INSERT … ON DUPLICATE KEY UPDATE`.
If `updated_at` is in the UPDATE clause it changes on every run, so every row reports as *updated*
and the criterion can never be met — the importer would look busy and idempotent at the same time,
which is worse than looking broken.

The model therefore requires a **ContentFingerprint** comparison before writing: a row is written
only when its fingerprint differs, and `updated_at` moves only with a real change. `unchanged` is
counted, not inferred. This is a domain rule, not a persistence detail, because "did this card
actually change?" is a question about the card.

## Domain Events

| Event | Trigger | Payload |
|---|---|---|
| **CatalogImportStarted** | a run is accepted | `import_id`, `source`, `started_at` |
| **CardAdded** | a Card with no prior natural-key match commits | `import_id`, `card_id`, `PrintingKey`, printing count |
| **CardUpdated** | a Card commits with a changed ContentFingerprint | `import_id`, `card_id`, changed field names |
| **PrintingAdded** | a new Printing attaches to an existing Card | `import_id`, `printing_id`, `PrintingKey` |
| **RecordRejected** | normalisation fails on a raw record | `import_id`, `reason_code`, `field`, `source_ref` |
| **SetCoverageIncomplete** | a run ends with distinct imported Printings < `sets.card_count` | `set_code`, `expected`, `imported`, `missing_numbers` |
| **CatalogImportFinished** | status becomes terminal | `import_id`, `status`, `ImportCounts`, `error_summary` |

`SetCoverageIncomplete` is the event that makes the unit brief's warning operational: coverage is
reported loudly rather than silently rounding completion up to 100%.

## Domain Services

| Service | Operations | Dependencies |
|---|---|---|
| **SourceAdapter** *(port, one implementation per source)* | `fetch(set_code) -> Iterable[RawRecord]`, `describe() -> SourceDescriptor` | Its own transport only. Adapters are **registered, not imported ad hoc** — adding a source is one file plus one config row, per the unit brief. Phase 1 ships `CsvSeedAdapter` reading version-controlled per-set files. |
| **Normaliser** | `normalise(RawRecord) -> CanonicalCard \| Rejection` | Vocabulary maps for Rarity/Finish/Edition. **Total and side-effect free**: never raises, never half-maps, never invents a default for a value it does not recognise. |
| **CatalogUpsert** | `upsert(CanonicalCard) -> Added \| Updated \| Unchanged` | Set/Card/Printing repositories. Keyed on `PrintingKey`; compares `ContentFingerprint`; writes the Card aggregate in one transaction. |
| **ImportRunner** | `run(source, sets) -> CatalogImport` | All of the above + CatalogImportRepository. Orchestrates fetch → normalise → upsert, accumulates `ImportCounts`, records rejections, emits the events, sets terminal status. Owns the `partial` decision when a source fails mid-run. |
| **CoverageReporter** | `coverage(set_code) -> CoverageReport` | Set + Printing repositories. Compares distinct imported collector numbers against `card_count`; the source of `SetCoverageIncomplete`. |

## Repository Interfaces

| Repository | Entity | Methods |
|---|---|---|
| **SetRepository** | Set | `get_by_code(code)`, `upsert(set)`, `list_all()` |
| **CardRepository** | Card *(aggregate root)* | `get_by_natural_key(set_id, collector_number)`, `save_with_printings(card, printings)`, `fingerprint_of(card_id)` |
| **PrintingRepository** | Printing | `get_by_key(PrintingKey)`, `list_for_card(card_id)`, `list_for_set(set_id)`, `set_price_tracking(printing_id, bool)` |
| **SealedProductRepository** | SealedProduct | `get(id)`, `upsert(product)`, `list_for_set(set_id)` |
| **CatalogImportRepository** | CatalogImport *(aggregate root)* | `start(source)`, `finish(import_id, status, counts, error_summary)`, `add_rejection(import_id, rejection)`, `list_recent(limit)`, `get_with_rejections(import_id)` |

Repositories return domain objects, not rows; `save_with_printings` is the only write path into the
Card aggregate, which is what keeps the whole-or-nothing rule enforceable in one place.

## Ubiquitous Language

| Term | Definition |
|---|---|
| **Set** | A released product line, identified by a code such as `FE01`. Its `card_count` is what the publisher printed. |
| **Card** | A named card independent of how it was printed. "Vipyro" is a Card. |
| **Printing** | **The SKU.** A specific physical version — Vipyro, Base, Holo Rare, 1st Edition, English. What a collector actually owns, what a price attaches to, what a listing sells. |
| **Finish** | The surface treatment (`normal`, `foil`, `reverse_foil`, `prismatic`). Distinct from Rarity, which is the print-run tier. |
| **Edition** | `first` or `unlimited`. A property of the Printing, not of the Set. |
| **Natural key** | `(set, collector_number, rarity, finish, language, edition)` — the identity of a Printing independent of our surrogate `id`. |
| **Canonical record** | A source record successfully mapped onto our model. The importer's unit of work. |
| **Rejection** | A source record that could not be mapped, kept whole with a reason. Never a partially imported card. |
| **Import run** | One execution of the importer against one source, recorded in `catalog_imports`. |
| **Unchanged** | A canonical record whose ContentFingerprint matches what is stored. The expected outcome of a re-run and an explicitly counted result. |
| **Coverage** | Distinct imported Printings in a Set against its printed `card_count`. Below 100% is reported, never rounded away. |
| **Seed** | The curated per-set CSV that is phase 1's source of truth (ADR-001). |
| **Adapter** | The per-source implementation of the fetch port. Adding a source means adding one. |

## Story coverage

| Story | Covered by |
|---|---|
| `007-catalog-schema` | Set, Card, Printing, SealedProduct entities; PrintingKey; Card aggregate boundary |
| `008-catalog-importer` | SourceAdapter, Normaliser, CatalogUpsert, ImportRunner; ContentFingerprint; whole-record rule |
| `009-import-run-reporting` | CatalogImport aggregate, ImportRejection, ImportCounts, all seven domain events, CoverageReporter |

## Open questions for Stage 2

1. **Fingerprint scope** — one per Card aggregate, or one per Card plus one per Printing? Per-aggregate is simpler; per-entity gives precise `printings_added` counts on an otherwise unchanged card. Leaning per-entity.
2. **`SetCoverageIncomplete` delivery** — an `app_logs` row at `warning`, an operator-console panel, or both? The console is story `034` in bolt 003, so bolt 002 may only log it.
3. **Seed file layout** — one CSV per set with a printings column group, or paired `{SET}-cards.csv` / `{SET}-printings.csv`? The second is more normalised; the first is far easier to hand-maintain, which is now the actual constraint.
