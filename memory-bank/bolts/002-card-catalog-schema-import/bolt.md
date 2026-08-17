---
id: 002-card-catalog-schema-import
unit: 002-card-catalog
intent: 001-collection-tracker
type: ddd-construction-bolt
status: partial
stories:
  - 007-catalog-schema
  - 008-catalog-importer
  - 009-import-run-reporting
created: 2026-08-09T12:00:00Z
started: 2026-08-09T20:00:00Z
completed: null
current_stage: done
stages_completed:
  - name: spike
    completed: 2026-08-10T09:00:00Z
    artifact: adr-001-catalog-data-source.md
  - name: model
    completed: 2026-08-10T10:30:00Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-08-10T12:00:00Z
    artifact: ddd-02-technical-design.md
  - name: implement
    completed: 2026-08-10T13:30:00Z
    artifact: backend/app/importer/, 0002_catalog.py, 6 models, 4 repositories, 3 services
  - name: test
    completed: 2026-08-10T14:20:00Z
    artifact: ddd-03-test-report.md

requires_bolts:
  - 001-platform-foundation
enables_bolts:
  - 003-card-catalog-surface
  - 004-inventory-core
requires_units: []
blocks: false

complexity:
  avg_complexity: 3
  avg_uncertainty: 3
  max_dependencies: 1
  testing_scope: 2
---

# Bolt: 002-card-catalog-schema-import

## Overview

The canonical catalog schema and the re-runnable importer that fills it. **The highest-uncertainty
bolt in the intent** — it is scheduled second precisely so that its unknowns surface while the
schema is still cheap to change.

## Objective

One real Elestrals set present in the database, complete and correct, imported by a process that is
idempotent, rate-limited, honest about rejections, and extensible to a new source by adding one
file.

## Stories Included

- **007-catalog-schema**: sets / cards / printings / sealed_products / catalog_imports (Must)
- **008-catalog-importer**: source adapters, normaliser, idempotent upsert (Must)
- **009-import-run-reporting**: run lifecycle and rejection reasons (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- ✅ **0. spike** *(timeboxed to 1 day — closed in under one)*: → `adr-001-catalog-data-source.md`

  **Outcome: No.** The data exists at usable fidelity, but the publisher's Terms of Use prohibit
  scraping, accessing the site to build a competing product, and reproducing site content — all
  three apply at once. Falling back to the curated CSV seed per this bolt's own decision rule. The
  canonical model and the idempotent upsert are unchanged; only the source of truth moves.

- ✅ **1. model**: Complete → `ddd-01-domain-model.md`

  6 entities, 10 value objects, 4 aggregates, 7 domain events, 5 domain services, 5 repositories.
  All three stories covered. **Human checkpoint — approve before Stage 2.**

- ✅ **2. design**: Complete → `ddd-02-technical-design.md`

  Layered per tech-stack, ports-and-adapters at the source seam only. All three Stage 1 open
  questions settled: per-entity fingerprints, coverage as log + API field, one CSV per set.
  **Human checkpoint — approve before Stage 3/4.**

- ⏭️ **3. ADR analysis** *(optional)*: **Recommended skip** — the one structural decision is
  already ADR-001, written during the spike.

- ✅ **4. implement**: Complete → `backend/app/importer/`, `0002_catalog.py`, 6 models,
  4 repositories, 3 services, admin controller, CLI, seed scaffold

- ⏳ **5. test**: **Partial** → `ddd-03-test-report.md`

  73 tests pass · bolt-002 modules 91% covered · migration validated as offline SQL.
  The zero-write re-run is asserted against emitted SQL, with the first run as a control.
  **Not met:** "one real set imported" — `FE01.csv` ships empty because ADR-001 rules out
  scraping and fabricating 126 cards would poison the catalog. Needs hand-compiled data,
  not code. **Not verified:** anything requiring a live MySQL.

  **The MySQL half closed on 2026-08-11** (`9eaa5a1`): migrations `0001`–`0003` applied clean to
  MySQL 8.4, `verify_mysql.py` 24/24, and a re-import over unchanged sources reported 0 added /
  0 updated / 5,000 unchanged against MySQL's own `ON DUPLICATE KEY UPDATE` — the idempotency
  claim the bolt rests on, previously asserted only against emitted SQL. Full import 34.4s
  against a 15-minute budget.

  **So this bolt is `partial` on exactly one thing, and it is not code:** nobody has compiled
  FE01's 126 cards. Until they do, the catalog is a working importer over an empty set.

## Dependencies

### Requires
- 001-platform-foundation (database, migrations, logging)

### Enables
- 003-card-catalog-surface
- 004-inventory-core — and therefore the entire rest of the intent

## Success Criteria

- [ ] One real set imported: every card, every printing, correct rarities — **the one open
      criterion.** `FE01.csv` ships with a header and no rows; this needs hand-compiled data
- [x] Second run over unchanged sources: 0 added, 0 updated — on MySQL's own
      `ON DUPLICATE KEY UPDATE`, 5,000 unchanged
- [x] A normalisation failure rejects the record whole, with a reason
- [~] `robots.txt` respected, rate limits enforced, real user agent with contact address —
      **moot for this bolt.** ADR-001 replaced the scraped source with a curated CSV seed, so
      nothing here fetches anything. The rule itself is live in `harvest/app/harvest/http.py`,
      where there *is* a scraper
- [x] Adding a source = one adapter file + one config row
- [x] Full re-import < 15 minutes — 34.4s at 5,000 cards
- [x] Fixture-driven normaliser tests per source
- [x] Coverage > 80% — 91% on this bolt's modules

## Notes

**The spike is stage zero and it is not optional.** Question: does a public source carry Elestrals
card data at printing-level fidelity — rarity, finish, language, edition — under terms we can live
with? Timebox one day.

- **Yes** → proceed as planned.
- **No** → fall back to the curated CSV seed. Same canonical model, same upsert, hand-maintained per
  set. Intent 001 continues; only the source of truth changes.

Either way the decision is made in week one, not discovered after the inventory UI is built on an
assumption. Record the outcome in `memory-bank/standards/decision-index.md`.

**Spike closed 2026-08-10 → the "No" branch.** Full reasoning, verbatim licence clauses and the
alternatives considered are in `adr-001-catalog-data-source.md`, indexed as ADR-001. Two findings
escalate beyond this bolt and are recorded there as follow-ups for the human:

1. An official first-party tracker already exists (`collect.elestrals.com`, Elestrals LLC). That is
   a product-positioning question, not an architecture one, and it was not known at inception.
2. It moves the brief's trademark/affiliation risk from theoretical to live.

Success criterion "one real set imported" now targets **FE01 Base (126 cards)** as the first
hand-compiled seed.
