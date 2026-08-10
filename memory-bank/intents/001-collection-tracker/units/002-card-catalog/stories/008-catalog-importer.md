---
id: 008-catalog-importer
unit: 002-card-catalog
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 002-card-catalog-schema-import
implemented: false
---

# Story: 008-catalog-importer

## User Story

**As an** operator
**I want** a re-runnable importer that turns public card data into our canonical catalog
**So that** a new Elestrals set becomes trackable without a code change, and a re-run never
duplicates anything

## Acceptance Criteria

- [ ] **Given** a configured source, **When** I run the importer for one real set, **Then** every card and every printing in that set exists with correct rarity, finish, language and edition
- [ ] **Given** the importer has already run, **When** I run it again over unchanged sources, **Then** 0 rows are added and 0 rows are updated
- [ ] **Given** a source record that fails normalisation, **When** it is processed, **Then** it is rejected **whole** with a reason, and no partial card or printing is written
- [ ] **Given** a source responds slowly or errors, **When** the run continues, **Then** the per-source rate limit is respected, retries use backoff, and the run ends `partial` rather than corrupting the catalog
- [ ] **Given** I want to add a new source, **When** I add one adapter file and one config row, **Then** it participates in the next run with no other code change
- [ ] **Given** any run, **When** it executes, **Then** it respects `robots.txt` and identifies itself with a real user agent and a contact address
- [ ] **Given** any run, **When** it executes, **Then** no user data is sent outbound — the importer reads external sources and writes our database, nothing else
- [ ] **Given** a full re-import of the whole catalog, **When** it runs, **Then** it completes in under 15 minutes

## Technical Notes

**This story carries the largest unknown in intent 001.** Bolt 002 opens with a timeboxed spike
against one real set, before the schema is committed. If public data proves too incomplete or its
terms too restrictive, the fallback is the curated CSV seed — same canonical model, same upsert,
hand-maintained per set. That decision needs to be forced in days, not discovered in weeks.

Architecture:

```
importer/
  sources/<name>.py     one adapter per source: fetch() -> raw records
  normalise.py          raw record -> CanonicalCard | Rejection
  upsert.py             idempotent write against natural keys
  runner.py             run lifecycle, rate limiting, run recording
```

- **Idempotency key**: `(set_code, collector_number, rarity, finish, language, edition)`. Implemented
  as `INSERT ... ON DUPLICATE KEY UPDATE` — never a read-then-write.
- Adapters are **registered**, not imported ad hoc, so the set of sources is data.
- `CanonicalCard` is a Pydantic model. Normalisation failures are typed rejections carrying the
  source record identity and a human-readable reason, both surfaced in `/admin/catalog`.
- `sets.card_count` is set from the **printed** set size, not from how many rows we managed to
  import. Deriving it from the import makes completion read 100% on an incomplete run — a wrong
  answer that looks right, which is worse than an obvious failure.
- Catalog rows are **soft-retired**, never hard-deleted. Inventory points at printings; deleting one
  out from under a user's holding is not an acceptable outcome of a data refresh.
- Store image URLs, never bytes, until written permission from the rights holder exists. A single
  config switch moves to storage-api afterwards.

## Dependencies

### Requires
- 007-catalog-schema
- 004-app-logging (run diagnostics are useless without it)

### Enables
- 009-import-run-reporting
- 010-card-search, 011-set-browser, 012-card-detail
- Everything in units 003–006 — there is nothing to own until the catalog exists

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Source changes its HTML structure | Adapter's normaliser rejects rows; run ends `partial`; rejections name the failing field |
| A card is renamed upstream | Matched on `(set, collector_number)`, name updated |
| A printing disappears upstream | Soft-retired, never deleted — a user may own it |
| Two sources disagree on a rarity | Source `weight` decides; the disagreement is logged at `warning` |
| A set is published with no collector numbers | Rejected wholesale with a clear reason; better no data than misaligned data |
| Run crashes mid-way | `catalog_imports` row remains `running` past a timeout and is swept to `failed`, so a crash is visible rather than silent |
| Two runs start concurrently | An advisory lock per source; the second run exits immediately as skipped |
| Source returns 429 | Backoff and continue; if it persists, end `partial` and surface it in the console |

## Out of Scope

- Price data — intent 002 has its own scraper framework, deliberately separate: the catalog changes
  a few times a year, prices change daily, and conflating them would couple two very different
  cadences and risk profiles
- Card images as bytes
- Automatic scheduling of imports beyond a simple daily trigger
