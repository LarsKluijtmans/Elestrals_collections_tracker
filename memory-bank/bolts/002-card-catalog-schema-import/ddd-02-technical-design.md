---
unit: 002-card-catalog
bolt: 002-card-catalog-schema-import
stage: design
status: complete
updated: 2026-08-10T13:35:00Z
---

# Technical Design - Card Catalog

Implements `ddd-01-domain-model.md` for stories `007-catalog-schema`, `008-catalog-importer`,
`009-import-run-reporting`. Source of truth is the curated CSV seed per `adr-001-catalog-data-source.md`.

**Scope boundary.** This bolt delivers the schema, the importer, and run reporting. The public
`GET /cards` and `GET /sets` surface and the operator console UI are stories 010–012 and 034 in
**bolt 003** — the tables and indexes they need are created here, the endpoints are not.

## The three questions Stage 1 left open

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | Fingerprint scope | **Per entity** — `content_fingerprint` on both `cards` and `printings` | Per-aggregate is simpler but collapses `printings_added` into "card updated". A new Holo printing of an otherwise unchanged card is exactly the event the operator needs to see. Per-entity also lets the upsert skip untouched printings individually rather than rewriting the set. |
| 2 | `SetCoverageIncomplete` delivery | **`app_logs` at `warning` + a computed `coverage` block on the run-detail response.** No UI. | The console is story 034 in bolt 003. Logging it now means the signal exists from the first import; putting it in the API response means bolt 003 builds a panel over data that is already there rather than adding a query later. |
| 3 | Seed file layout | **One CSV per set, one row per printing**, card fields repeated across a card's rows | Hand-maintainability is now the binding constraint (ADR-001), and one file per set is what a human actually edits. The cost is redundancy — handled explicitly under *Normalisation* below. |

## Architecture Pattern

**Layered, exactly as `standards/tech-stack.md` mandates — with ports and adapters applied to one
seam only: the source.**

```
Controllers → Services → Repositories → SQLAlchemy models → MySQL
```

The layering rule is non-negotiable across the codebase, and the read paths here are ordinary. The
one place hexagonal structure earns its keep is `SourceAdapter`: the unit brief requires that adding
a source be "one adapter file plus one config row", and ADR-001 makes that portability the whole
point — today's seed must be replaceable by a licensed API without touching a domain rule.

Everything else stays plain. No repository abstraction over the abstraction, no CQRS, no event bus:
the domain events from Stage 1 are emitted as structured `log_event()` calls and run counters, not
as an in-process publish/subscribe machine nothing subscribes to yet.

## Layer Structure

```text
┌──────────────────────────────────────────────────────────────┐
│ Presentation    controllers/admin_catalog.py                 │
│                 importer/cli.py  (python -m app.importer)    │
├──────────────────────────────────────────────────────────────┤
│ Application     services/import_runner.py                    │
│                 services/catalog_upsert.py                   │
│                 services/coverage_service.py                 │
├──────────────────────────────────────────────────────────────┤
│ Domain          importer/normaliser.py                       │
│                 importer/fingerprint.py                      │
│                 importer/vocabulary.py                       │
│                 importer/canonical.py   (Pydantic VOs)       │
├──────────────────────────────────────────────────────────────┤
│ Infrastructure  importer/sources/__init__.py   (registry)    │
│                 importer/sources/csv_seed.py   (adapter)     │
│                 repositories/{set,card,printing,catalog_import}_repository.py │
│                 models/{set,card,printing,sealed_product,catalog_import,import_rejection}.py │
│                 data/catalog/FE01.csv          (the seed)    │
│                 alembic/versions/0002_catalog.py             │
└──────────────────────────────────────────────────────────────┘
```

Responsibilities, held to the tech-stack rules: controllers are thin and never touch a session;
`import_runner` holds orchestration and never opens one directly; repositories are the only code
that talks to the DB; `normaliser` is pure and importable with no database at all — which is what
makes fixture-driven normaliser tests possible without a MySQL instance.

## Source adapter contract

```python
class SourceAdapter(Protocol):
    name: str                                    # registry key, matches catalog_imports.source
    def describe(self) -> SourceDescriptor: ...  # display name, terms_url, requires_network
    def fetch(self, set_code: str) -> Iterable[RawRecord]: ...
```

Adapters register by decorator into `SOURCES: dict[str, SourceAdapter]`; `import_runner` resolves by
name and never imports an adapter module directly. Adding a source is a new file and a config row,
as required.

`SourceDescriptor.requires_network` is the hook for the constraints the unit brief places on future
scrapers — `robots.txt` compliance, conservative rate limits, a real user agent with a contact
address. **`CsvSeedAdapter` sets it `False`, so none of that machinery ships in phase 1.** That is a
direct consequence of ADR-001 and worth stating plainly: the importer currently makes no outbound
requests at all.

## Seed format and normalisation

`backend/data/catalog/FE01.csv`, one row per **printing**:

```csv
set_code,collector_number,name,card_type,element,rune_type,attack,defence,spirit_cost,rarity,finish,language,edition,image_url
FE01,BS1-001,Teratlas,elestral,earth,,2400,2100,"{""earth"":2}",holo_rare,foil,en,first,https://...
FE01,BS1-001,Teratlas,elestral,earth,,2400,2100,"{""earth"":2}",rare,normal,en,first,https://...
```

The normaliser groups rows by `(set_code, collector_number)` and emits one `CanonicalCard` per
group, with one Printing per row.

**The redundancy has a failure mode, and it is handled rather than tolerated:** if two rows share a
collector number but disagree on a card-level field — a typo in `attack` on the second row — the
whole card is rejected with `conflicting_card_fields`, naming the field and both values. Silently
taking the first row would write a card whose data depends on file ordering. Per Stage 1: reject
whole, never half-write.

Other rejection paths, all `reason_code`s on `import_rejections`:

| `reason_code` | Trigger |
|---|---|
| `unknown_rarity` / `unknown_finish` / `unknown_edition` | value not in the closed vocabulary — never defaulted |
| `conflicting_card_fields` | rows of one card disagree on a card-level field |
| `missing_required_field` | no `collector_number`, `name`, `card_type`, or `rarity` |
| `invalid_spirit_cost` | not a JSON object of element → non-negative int |
| `type_field_mismatch` | `attack`/`defence` on a non-elestral, `rune_type` on a non-rune, etc. |
| `duplicate_printing_key` | two rows produce an equal `PrintingKey` within one file |

## Idempotency — the mechanism

The bolt criterion is *second run over unchanged sources: 0 added, 0 updated*. Stage 1 established
that `INSERT … ON DUPLICATE KEY UPDATE` cannot deliver it while `updated_at` is in the UPDATE clause.
Concretely:

1. `fingerprint(entity)` = SHA-256 over the entity's meaningful fields in a fixed order, excluding
   `id`, `created_at`, `updated_at`. Stored as `CHAR(64)`.
2. Upsert reads the existing `content_fingerprint` by natural key.
   - no row → `INSERT`, count **added**
   - row, fingerprint equal → **no SQL is issued at all**, count **unchanged**
   - row, fingerprint differs → `UPDATE` the changed entity only, bump `updated_at`, count **updated**
3. A card and its printings commit in one transaction (`save_with_printings`); batches of 500 cards
   share a connection but each card's write is its own transaction boundary, so a mid-batch failure
   leaves every prior card whole.

A re-run over an unchanged set therefore issues only `SELECT`s. That is directly assertable in a
test — the acceptance test counts write statements, not just the reported totals, because the
counters could lie while the criterion is met by accident.

## API Design

Operator-only, under the `GET /api/v1/admin/catalog/*` slot already reserved in
`standards/api-conventions.md`.

| Endpoint | Method | Auth | Request | Response |
|---|---|---|---|---|
| `/api/v1/admin/catalog/imports` | `GET` | operator | `?limit`&`cursor`&`status`&`source` | `{ items: ImportRunSummary[], next_cursor, total }` |
| `/api/v1/admin/catalog/imports/{id}` | `GET` | operator | — | `ImportRunDetail` incl. `counts`, `coverage[]`, `rejections[]` (cursor-paged) |
| `/api/v1/admin/catalog/imports` | `POST` | operator | `{ source, set_codes[] }` | `202` + `ImportRunSummary` — enqueues, returns immediately |

```jsonc
// ImportRunDetail
{
  "id": "…", "source": "csv_seed", "status": "success",
  "started_at": "2026-08-10T13:00:00Z", "finished_at": "2026-08-10T13:00:04Z",
  "counts": { "sets_seen": 1, "cards_added": 126, "cards_updated": 0,
              "cards_unchanged": 0, "printings_added": 189, "rejected": 0 },
  "coverage": [ { "set_code": "FE01", "expected": 126, "imported": 126, "missing_numbers": [] } ],
  "rejections": { "items": [ { "source_ref": "FE01.csv:42", "reason_code": "unknown_rarity",
                               "field": "rarity", "message": "…", "raw_record": {…} } ],
                  "next_cursor": null, "total": 0 }
}
```

Cursor pagination, `snake_case` stable error codes, ISO-8601 UTC — all per the conventions doc. The
CLI (`python -m app.importer --source csv_seed --set FE01`) shares `import_runner` with the POST
endpoint, so there is one execution path, not two.

**One additive change to `api-conventions.md`:** a new error code `import_run_not_found`. Additive
only, consistent with the versioning rule.

## Data Persistence

Migration `alembic/versions/0002_catalog.py`, following `standards/data-model.md` exactly, plus the
two fingerprint columns this design adds.

| Table | Columns | Relationships |
|---|---|---|
| `sets` | `id`, `code` UQ, `name`, `series`, `released_on`, `card_count`, `logo_asset_url`, timestamps | ← `cards`, `sealed_products` |
| `cards` | `id`, `set_id` FK, `collector_number`, `name`, `card_type`, `element`, `rune_type`, `subtype`, `attack`, `defence`, `spirit_cost` JSON, `rules_text`, `flavour_text`, `artist`, **`content_fingerprint CHAR(64)`**, timestamps | → `sets`; ← `printings` |
| `printings` | `id`, `card_id` FK, `rarity`, `finish`, `language`, `edition`, `image_url`, `is_tracked_for_price`, **`content_fingerprint CHAR(64)`**, timestamps | → `cards`; ← inventory/prices/listings later |
| `sealed_products` | `id`, `set_id` FK NULL, `kind`, `name`, `contents_note`, `image_url`, `is_tracked_for_price` | → `sets` |
| `catalog_imports` | `id`, `source`, `started_at`, `finished_at` NULL, `status`, `sets_seen`, `cards_added`, `cards_updated`, `cards_unchanged`, `printings_added`, `rejected`, `error_summary` TEXT | ← `import_rejections` |
| `import_rejections` | `id`, `import_id` FK, `source_ref`, `raw_record` JSON, `reason_code`, `field` NULL, `message`, `created_at` | → `catalog_imports` |

**Constraints and indexes**

- `UNIQUE (set_id, collector_number)` on `cards` — the card natural key
- `UNIQUE (card_id, rarity, finish, language, edition)` on `printings` — **the `PrintingKey`, and the
  guarantee that makes the upsert idempotent under concurrency, not just under sequence**
- `INDEX (name)` on `cards` for bolt 003's prefix search; `INDEX (card_type, element)` for filters
- `INDEX (import_id, reason_code)` on `import_rejections` for the console's grouped view
- `INDEX (status, started_at DESC)` on `catalog_imports` for the run list
- `cards_added` etc. are `INT UNSIGNED NOT NULL DEFAULT 0` — a run always has counts, never NULL

`cards_unchanged` is new relative to `data-model.md`, which lists the counter set without it. It is
required by the idempotency criterion — "unchanged" is a reported success signal, not the absence of
a number. Flagged as an additive change to that standard.

## Security Design

| Concern | Approach |
|---|---|
| Authentication | JWKS-validated bearer, `RS256`, `iss` pinned — `app/security.py` reused verbatim, unchanged from bolt 001 |
| Authorization | `/admin/catalog/*` requires the operator role from the validated token. A non-operator gets `403`, never a filtered-down `200` |
| Catalog reads | Public and cacheable in bolt 003; they must never vary on a user. Nothing in this bolt reads a user table |
| Outbound data | The importer sends **no** user data outbound. With `CsvSeedAdapter` it makes no outbound request at all |
| Untrusted input | The seed is version-controlled and reviewed, but still fully validated — bounded row count, bounded field lengths, JSON parsed not `eval`'d. A trusted-source assumption is exactly how a supply-chain problem enters |
| Image rights | `image_url` stores a URL, never bytes (ADR-001 and the brief's trademark risk) |
| Logging | Import events go through `log_event()`, the single writer from bolt 001. `raw_record` on a rejection is stored after passing through the same `redact()` path — a source file could contain anything |

## NFR Implementation

| Requirement | Design Approach |
|---|---|
| Full re-import < 15 min | Seed is a local file, so the bound is DB writes. ~5k cards / ~50k printings at 500-card batches, fingerprint-gated. First run is the only write-heavy one |
| Second run: 0 added, 0 updated | Fingerprint comparison; unchanged entities issue no SQL. Asserted by counting write statements, not by trusting counters |
| Search p95 < 150ms | Indexes created here; the queries and their measurement are bolt 003 |
| Source fails mid-run → `partial`, catalog consistent | Per-card transactions mean the catalog is never half-written. The run is marked `partial` with `error_summary`; already-committed cards stay |
| Coverage never silently 100% | `sets.card_count` comes from the *printed* size in the seed header, never from imported rows. `CoverageReporter` compares and emits `SetCoverageIncomplete` at `warning` |
| Reliability of counters | Counters accumulate in the run aggregate and are written once at terminal status, not incremented per row — a crash cannot leave a half-counted run claiming success |

## Error Handling

| Error Type | Code | Response |
|---|---|---|
| Unknown import run | `import_run_not_found` | `404` + standard error shape *(new code — additive)* |
| Unknown set on POST | `set_not_found` | `404` |
| Non-operator caller | — | `403`, standard shape, no body detail |
| Row fails normalisation | `import_row_rejected` | Not an HTTP error — recorded as an `import_rejections` row; the run continues |
| Adapter raises mid-run | — | Run → `partial`, `error_summary` set, `critical` log row, `500` only if triggered synchronously |
| Rate limit | `rate_limited` | `429` + `Retry-After` |

A rejected row is deliberately *not* an API error. The run's job is to import what it can and report
what it could not — story 009 is that report.

## External Dependencies

| Service | Purpose | Integration |
|---|---|---|
| MySQL 8 (`elestrals`) | the catalog itself | SQLAlchemy 2.x, existing engine from bolt 001 |
| logs-api | import errors and coverage warnings | via `log_event()` — already bounded and non-blocking from bolt 001 |
| **Card data sources** | **none in phase 1** | The unit brief's "High risk — completeness, fidelity and terms unverified" is **closed** by ADR-001. The importer has no network dependency until a licensed adapter is added |

## Traceability

| Story | Delivered by |
|---|---|
| `007-catalog-schema` | `0002_catalog.py`, six models, `PrintingKey` uniqueness, indexes |
| `008-catalog-importer` | `SourceAdapter` + registry, `CsvSeedAdapter`, `normaliser`, `fingerprint`, `catalog_upsert`, `import_runner`, CLI |
| `009-import-run-reporting` | `catalog_imports` + `import_rejections`, `CoverageReporter`, three admin endpoints |

## Stage 3 (ADR analysis) — recommendation

**Skip it.** The one decision of architectural weight in this bolt — where the catalog comes from —
is already captured as ADR-001, written during the spike. The choices made here (fingerprint scope,
seed layout, coverage delivery) are design detail recorded above, not structural commitments needing
their own records. Stage 3 is marked optional in the bolt type; going straight to Stage 4 is the
honest call rather than manufacturing an ADR to fill a stage.
