---
unit: 002-card-catalog
intent: 001-collection-tracker
phase: inception
status: in-progress
created: '2026-08-09T12:00:00Z'
updated: '2026-08-09T12:00:00Z'
---

# Unit Brief: card-catalog

## Purpose

Own the canonical Elestrals catalog: sets, cards, printings and sealed products, populated by a
re-runnable importer from public sources, and exposed through search and browse APIs and pages.
Every later feature — inventory, completion, valuation, listings — resolves through `printings`.

## Scope

### In Scope
- Catalog schema and migrations
- A source-adapter architecture: one adapter per external source, a shared normaliser, one
  idempotent upsert
- Import run recording, rejection reasons, and the operator console over both
- Card search (prefix, ranked) and browse filters
- `/sets`, `/sets/:code`, `/cards/:id` pages
- Sealed product catalog rows (the *products*, not anyone's inventory)

### Out of Scope
- Anyone's ownership of anything (unit 003)
- Prices (intent 002) — but `is_tracked_for_price` is set here
- Hosting card images — we store URLs only

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-5 | Import the card catalog | Must |
| FR-6 | Search and browse the catalog | Must |
| FR-17 | Operator catalog console | Should |

---

## Domain Concepts

### Key Entities
| Entity | Description | Attributes |
|--------|-------------|------------|
| Set | A released product line | `code`, `name`, `series`, `released_on`, `card_count` |
| Card | A named card, independent of how it was printed | `name`, `card_type`, `element`, `rune_type`, `attack`, `defence`, `spirit_cost`, `rules_text` |
| **Printing** | **The SKU.** A specific physical version | `rarity`, `finish`, `language`, `edition` |
| SealedProduct | Pack, box, deck, bundle | `kind`, `name`, `contents_note` |
| CatalogImport | One importer run | `source`, `status`, counts, `error_summary` |

### Key Operations
| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `fetch(source)` | Pull raw records from one source | source config | raw records |
| `normalise` | Map a raw record onto the canonical model | raw record | `CanonicalCard` or `Rejection` |
| `upsert` | Idempotent write keyed on the natural key | canonical records | added / updated / unchanged counts |
| `search_cards` | Ranked prefix search | query, filters | ranked cards |
| `get_set_checklist` | Every printing in a set | set code | printings |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 7 |
| Must Have | 6 |
| Should Have | 1 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 007-catalog-schema | Catalog schema and migrations | Must | Planned |
| 008-catalog-importer | Re-runnable catalog importer | Must | Planned |
| 009-import-run-reporting | Import runs and rejections | Must | Planned |
| 010-card-search | Ranked card search | Must | Planned |
| 011-set-browser | Set gallery and checklist | Must | Planned |
| 012-card-detail | Card detail with all printings | Must | Planned |
| 034-admin-catalog-console | Operator catalog console | Should | Planned |

---

## Dependencies

### Depends On
| Unit | Reason |
|------|--------|
| 001-platform-foundation | DB, migrations, logging, RBAC for the operator console |

### Depended By
| Unit | Reason |
|------|--------|
| 003, 004, 005, 006 | Inventory points at `printings`; there is nothing to own until this exists |

### External Dependencies
| System | Purpose | Risk |
|--------|---------|------|
| Public card-data sources | the catalog itself | **High** — completeness, fidelity and terms are all unverified. This is the intent's largest unknown |

---

## Technical Context

### Suggested Technology
`httpx` async fetching with per-source rate limits; `selectolax` or `beautifulsoup4` for HTML;
Pydantic models as the canonical intermediate; a single `upsert()` using
`INSERT ... ON DUPLICATE KEY UPDATE` against the natural keys. Adapters live in
`backend/app/importer/sources/` and are registered, not imported ad hoc, so adding a source is a
new file plus a row of config.

### Integration Points
| Integration | Type | Protocol |
|-------------|------|----------|
| Card data sources | outbound scrape/API | HTTPS, rate-limited, allowlisted hosts |
| Frontend | API | REST `/api/v1/cards`, `/api/v1/sets` |

### Data Storage
| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| `sets` | SQL | tens | permanent |
| `cards` | SQL | ~5k | permanent |
| `printings` | SQL | ~50k | permanent |
| `catalog_imports` | SQL | one per run | 1 year |

---

## Constraints

- **Idempotency is a hard requirement, not a nice-to-have.** The natural key is
  `(set, collector_number, rarity, finish, language, edition)`. Two runs over unchanged sources must
  produce zero writes.
- A record that fails normalisation is **rejected whole**, with a reason. Never half-write a card.
- Scrapers respect `robots.txt` and a conservative rate limit, and identify themselves with a real
  user agent and contact address.
- No user data is ever sent outbound by the importer.
- Store image URLs, never bytes, until permission exists.

---

## Success Criteria

### Functional
- [ ] Import one real set end to end, with every printing and correct rarities
- [ ] Second run over unchanged data: 0 added, 0 updated
- [ ] Rejected rows are listed with reasons in `/admin/catalog`
- [ ] Search for a 3-character prefix returns ranked results with set and rarity
- [ ] A card detail page lists every printing of that card
- [ ] A non-operator receives 403 from `/admin/catalog`

### Non-Functional
- [ ] Search p95 < 150ms with the full catalog loaded
- [ ] A full re-import completes in < 15 minutes
- [ ] A source failing mid-run marks the run `partial` and leaves the catalog consistent

### Quality
- [ ] Code coverage > 80%, including a fixture-driven normaliser test per source
- [ ] All acceptance criteria met
- [ ] Code reviewed and approved

---

## Bolt Suggestions

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| 002-card-catalog-schema-import | DDD | 007, 008, 009 | Schema + importer + run reporting. **Begins with a timeboxed spike** against one real set before any schema is committed. |
| 003-card-catalog-surface | DDD | 010, 011, 012, 034 | Search, browse, card detail, operator console |

---

## Notes

**This unit is where intent 001 can fail.** If public Elestrals data is too incomplete or its terms
too restrictive, the fallback is the curated CSV seed — same schema, same upsert, hand-maintained
per set. The spike at the head of bolt 002 exists to force that decision within days rather than
weeks, while the schema is still cheap to change.

Set `card_count` from the *printed* set size, not from how many rows we managed to import.
Otherwise completion silently reads 100% on an incomplete import — a wrong answer that looks right,
which is worse than an obvious failure.
