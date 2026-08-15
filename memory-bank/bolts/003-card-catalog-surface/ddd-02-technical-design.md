---
unit: 002-card-catalog
bolt: 003-card-catalog-surface
stage: design
status: complete
updated: 2026-08-10T15:10:00Z
---

# Technical Design - Card Catalog Surface

Implements `ddd-01-domain-model.md` for `010-card-search`, `011-set-browser`, `012-card-detail`,
`034-admin-catalog-console`.

## A correction to Stage 1

Stage 1 defined a `word_prefix` tier and illustrated it with *"atlas" matching "Teratlas"*. Those
are two different things: "atlas" is not a word prefix of "Teratlas", it is an **infix**. A
collector typing a fragment they half-remember wants the infix behaviour, so the tier list gains
a distinct lowest tier rather than quietly redefining `word_prefix`:

| Tier | `MatchKind` | Matches |
|---|---|---|
| 1 | `exact_name` | `name = term` |
| 2 | `name_prefix` | `name LIKE 'term%'` — index-assisted |
| 3 | `word_prefix` | a word inside the name starts with the term — `name LIKE '% term%'` |
| 4 | `collector_number` | `collector_number LIKE 'term%'` |
| 5 | `set_code` | `set.code = term` |
| 6 | `infix` | `name LIKE '%term%'` — the "Teratlas" case |

## The three questions Stage 1 left open

| # | Question | Decision |
|---|---|---|
| 1 | Search implementation | **Plain indexed SQL with a `CASE` tier expression.** No FULLTEXT, no token table. |
| 2 | Completion ring hydration | **`/sets` stays anonymous and cacheable**; completion comes from bolt 004's `/api/v1/completion` and merges client-side. `CompletionRing` takes `number \| null`. |
| 3 | Primary printing | Lowest tier of an explicit `RARITY_ORDER`, tie-broken by `(finish, edition, printing_id)`. **Fallback is "whatever the lowest available tier is"**, so a card whose only printing is `secret` shows that. |

### Why not FULLTEXT, and when to revisit

The catalog is **~5,000 cards** (`unit-brief.md` data volumes). At that size a full scan in MySQL
is single-digit milliseconds, against a 150ms p95 budget. Both alternatives cost more than they
return today:

- **FULLTEXT** brings `innodb_ft_min_token_size` (3 by default, so two-character searches silently
  return nothing), stopword lists, and a relevance score that would fight the explicit tier
  ordering the domain model requires. We would be ranking twice and explaining the disagreement.
- **A `card_search_terms` token table** gives precise tiers but must be kept in step with the
  importer, which means either coupling bolt 002's upsert to a bolt-003 projection or accepting a
  table that can go stale. Both are real costs to buy performance we do not need.

Tiers 1, 2 and 4 use the existing `ix_cards_name` / natural-key indexes. Tiers 3 and 6 are scans
that MySQL performs over a few thousand rows.

**Revisit trigger, written down so it is not a judgement call later:** measured p95 above 100ms,
or the catalog passing 100,000 cards. Because `MatchKind` is a domain concept rather than a
storage detail, swapping the implementation then changes no API and no test assertion about
ordering.

## Architecture Pattern

Unchanged: `Controllers → Services → Repositories → SQLAlchemy → MySQL`, per `tech-stack.md`.

This bolt adds no new pattern. Read models are assembled in services from repository results;
they are Pydantic response models, not ORM entities, which is what keeps the public contract
independent of the write schema.

## Layer Structure

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Presentation   controllers/catalog.py        public: cards, sets     │
│                controllers/admin_catalog.py  (extend) + /health      │
│                frontend/src/pages/{Sets,SetDetail,CardDetail,        │
│                                    AdminCatalog}.tsx                 │
│                frontend/src/components/{CardSearchBox,CompletionRing,│
│                            ElementChip,RarityMaterial,PrintingTable} │
├──────────────────────────────────────────────────────────────────────┤
│ Application    services/card_search_service.py                       │
│                services/set_browse_service.py                        │
│                services/card_detail_service.py                       │
│                services/catalog_health_service.py                    │
├──────────────────────────────────────────────────────────────────────┤
│ Domain         services/alt_text.py            pure                  │
│                services/rarity_order.py        pure, shared with UI  │
├──────────────────────────────────────────────────────────────────────┤
│ Infrastructure repositories/{card,set,printing,catalog_import}_*.py  │
│                (extended — no new repository classes)                │
└──────────────────────────────────────────────────────────────────────┘
```

## API Design

All four public endpoints are already reserved in `standards/api-conventions.md`.

| Endpoint | Method | Auth | Request | Response |
|---|---|---|---|---|
| `/api/v1/cards` | `GET` | public | `q`, `set_code[]`, `element[]`, `card_type[]`, `rarity[]`, `limit`, `cursor` | `{ items: CardSearchResult[], next_cursor, total }` |
| `/api/v1/cards/{card_id}` | `GET` | public | — | `CardDetail` |
| `/api/v1/sets` | `GET` | public | `series` | `{ items: SetSummary[] }` |
| `/api/v1/sets/{code}` | `GET` | public | `limit`, `cursor` | `SetChecklist` |
| `/api/v1/admin/catalog/health` | `GET` | operator | — | `CatalogHealth` |

```jsonc
// CardSearchResult — deterministic, and the contract bolt 005 selects from
{
  "card_id": "…", "name": "Teratlas", "set_code": "FE01", "collector_number": "BS1-001",
  "card_type": "elestral", "element": "earth",
  "primary_printing": { "printing_id": "…", "rarity": "rare", "finish": "normal",
                        "language": "en", "edition": "first", "image_url": null,
                        "alt_text": "Teratlas — FE01 rare" },
  "printing_count": 2,
  "match_kind": "name_prefix"        // shown in the UI; also makes ranking testable
}
```

`match_kind` is on the wire deliberately: it is what lets a test assert *why* a row ranked where
it did, rather than asserting an opaque position.

**Filter algebra** follows `api-conventions.md` — repeated params OR within an attribute, distinct
params AND across attributes — so the URL-serialised UI filters and the API cannot drift.

**Additive change to `api-conventions.md`:** one new error code, `card_not_found`. The existing
list has `printing_not_found` and `set_not_found` but no card-level code.

**Empty-query rule.** `q` shorter than 2 characters returns `{items: [], total: 0}` without
touching the database. Search-as-you-type fires on the first keystroke, and a one-character
prefix matches a third of the catalog — work thrown away before it renders.

### Caching

Public responses carry `Cache-Control: public, max-age=300, stale-while-revalidate=3600` and no
`Vary: Authorization`. That is only sound because these responses genuinely do not vary on the
user — which is the whole reason completion is not in `SetSummary`. If a user-specific field were
ever added to one of these, the cache header would silently start serving one collector's data
to another.

## Data Persistence

**No migration.** This bolt reads bolt 002's schema. `ix_cards_name` (tiers 1–3, 6),
`ix_cards_type_element` (filters) and `uq_cards_set_number` (tier 4) already exist.

Two query shapes matter:

| Query | Approach |
|---|---|
| Set summaries with imported counts | One `LEFT JOIN` + `GROUP BY`, not a count per set. 30 sets today, but N+1 is a habit not a threshold |
| Printings for a page of search results | `PrintingRepository.list_for_cards(card_ids)` — one `IN` query, so a 50-row page is 2 queries rather than 51 |

## Frontend Design

| Component | Responsibility |
|---|---|
| `CardSearchBox` | **The contract bolt 005 consumes.** Debounced query, arrow-key navigation, `Enter` selects, `Escape` clears. Emits `onSelect(CardSearchResult)`; it does not know what the consumer does with it. `role="combobox"` + `aria-activedescendant` |
| `CompletionRing` | `completion: number \| null`. `null` renders the ring track only — the signed-out and pre-bolt-004 state |
| `ElementChip` | Hue **plus the element name**. Never colour alone (ux-guide §9) |
| `RarityMaterial` | Flat / ring / gradient / sheen / iridescent per ux-guide §4. Carries a text label; all sheen suppressed under `prefers-reduced-motion` |
| `PrintingTable` | Every printing of a card, rarity as material, element as chip — the four encodings kept independent |

Server state via TanStack Query per `tech-stack.md`; the search box keys its query on the
debounced term so an in-flight request for a stale prefix cannot overwrite a newer result.

### The keyboard contract, stated once

`ux-guide.md` §12 makes add-a-card one of the two interactions worth over-investing in: three
characters → arrow → `Enter`, under five seconds, hands never leaving the keyboard. That flow is
bolt 005, but its search half is built here. Specified now so bolt 005 consumes rather than
reworks:

- `↓`/`↑` move the active row and never wrap silently past the ends
- `Enter` selects the active row; with no active row it selects the first
- `Escape` clears the term and keeps focus
- The active row is `aria-activedescendant`, so a screen reader announces it
- Ordering is stable between renders — the total order from Stage 1 is what makes `Enter` safe

## Security Design

| Concern | Approach |
|---|---|
| Public reads | `/cards`, `/sets` and their detail routes serve unauthenticated and are cacheable. They read no user table and take no `Principal` |
| Operator console | `/admin/catalog/health` reuses `require_operator`; a non-operator gets `403` with no body detail |
| Cache safety | No `Vary: Authorization` because no public response varies on the caller — enforced by these endpoints having no user-scoped dependency at all |
| Injection | Filters are bound parameters; `LIKE` terms are escaped for `%` and `_` so a search for `100%` is a literal, not a wildcard |
| Enumeration | Card and set ids are already public catalog facts; there is nothing to leak by enumerating them |

## NFR Implementation

| Requirement | Design Approach |
|---|---|
| 3-char prefix < 150ms p95 | Indexed prefix for the common tiers over ~5k rows; batched printing hydration; measured before claiming |
| Stable ranked order | Total sort key `(match_kind, released_on desc, collector_number asc, card_id asc)`, asserted in tests |
| All three public pages work signed out | No authenticated dependency in their route graph; a test hits them with no `Authorization` header at all |
| WCAG 2.2 AA | Central `alt_text` = `"{name} — {set} {rarity}"`; element chips carry names; visible focus; reduced-motion respected |
| Coverage > 80% | Services and ranking are pure enough to test without a browser; the keyboard contract is tested at component level |

## Error Handling

| Error Type | Code | Response |
|---|---|---|
| Unknown card | `card_not_found` | `404` *(new code — additive)* |
| Unknown set | `set_not_found` | `404` |
| `q` under 2 characters | — | `200` with an empty page, not an error. A user mid-type has not made a mistake |
| Malformed cursor | `bad_request` | `400` |
| Non-operator on `/health` | — | `403`, no detail |

## Traceability

| Story | Delivered by |
|---|---|
| `010-card-search` | `GET /cards`, `CardSearchService`, tier `CASE`, `CardSearchBox` |
| `011-set-browser` | `GET /sets`, `GET /sets/{code}`, `SetBrowseService`, `Sets.tsx`, `SetDetail.tsx`, `CompletionRing` |
| `012-card-detail` | `GET /cards/{id}`, `CardDetailService`, `CardDetail.tsx`, `PrintingTable` |
| `034-admin-catalog-console` | `GET /admin/catalog/health`, `CatalogHealthService`, `AdminCatalog.tsx` |

## Stage 3 (ADR analysis) — recommendation

**One ADR is warranted:** the search implementation. Choosing scan-and-rank over FULLTEXT is a
real architectural commitment with a stated revisit trigger, and the next person to look at
search performance needs the reasoning rather than an archaeology exercise. It will be
`adr-002-search-implementation.md`.

Nothing else here rises above design detail.
