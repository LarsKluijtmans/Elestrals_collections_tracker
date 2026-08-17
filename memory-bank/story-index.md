---
updated: 2026-08-17T19:00:00Z
mode: single-file
---

# Story Index

Project-wide story tracking. **70 stories** across intents 001 and 002 — **47 implemented**, 3
partial, 3 blocked, 17 not built. Full breakdown under [Counts](#counts).

**This file was wrong until 2026-08-17, and it is worth knowing how.** It recorded intent 001's 36
stories as `planned` while four of its bolts had shipped, been tested and been verified against real
MySQL. The reason was not carelessness: `status-integrity.cjs` was reporting *zero* inconsistencies,
because a CRLF working tree made its LF-only frontmatter regex skip 10 of the 17 bolt files without
saying so. It was scanning 7 bolts and calling the result clean. Once the line endings were
normalised the same command found **37 real inconsistencies**, 26 of them intent 002's own stories
left `ready` under `complete` bolts. See `maintenance-log.md` for the whole diagnosis.

The lesson is already written down elsewhere in this repo, from bolt 013: *a test that silently
checks nothing is worse than no test.* This is the second tool it has been true of.

Intent 002 was elaborated on 2026-08-15, when ADR-004 (scrape rather than licence) and the
second-backend decision took it into construction, and **built the same day** — 27 of its 34 stories
are implemented, 3 partial and 4 blocked on phase-1 work that has not shipped
(`collection_snapshots`, `/collection`, the outbox).

Intent 001's phase-1 work is what those four wait on: bolts 001–005 are built (001, 002, 003 and 005
`partial`, 004 `complete`), and bolts 006–009 have not been started.

Intent 003 remains decomposed to unit level only; its stories are enumerated in its `units.md`.
**Intent 004 (card scanning)** was created on 2026-08-17 and is blocked at inception Checkpoint 1 on
four unanswered questions — no units, no stories, nothing to index yet.

## Status vocabulary

| In the tables | Means |
|---|---|
| `implemented` | acceptance criteria met and tested |
| `partial` | some criteria met; what is missing is named in the bolt's construction result |
| `blocked` | cannot proceed until something else ships. The dependency is always named |
| `not built` / `planned` | nothing written. `planned` is intent 001's word for it, `not built` intent 002's — they mean the same and are counted together below |

A **bolt** may be `partial` while every one of its stories is `implemented`, when what is open is a
bolt-level criterion rather than a story. Bolt 005 is exactly that: all three stories done, and the
timed session with a real person not run.

The story *files* carry `status: complete` + `implemented: true`, which is
`status-integrity.cjs`'s vocabulary rather than this table's. The script owns those; this table is
the human-readable view and distinguishes states the script has no word for.

## Intent 001 — collection-tracker

| Story | Unit | Bolt | Priority | Status |
|---|---|---|---|---|
| 001-sign-in-with-platform | 001-platform-foundation | 001 | must | implemented |
| 002-app-shell-and-routing | 001-platform-foundation | 001 | must | implemented |
| 003-branding-driven-theme | 001-platform-foundation | 001 | must | implemented |
| 004-app-logging | 001-platform-foundation | 001 | must | implemented |
| 005-platform-log-forwarding | 001-platform-foundation | 001 | must | implemented |
| 006-usage-metering | 001-platform-foundation | 001 | must | implemented |
| 007-catalog-schema | 002-card-catalog | 002 | must | implemented |
| **008-catalog-importer** | 002-card-catalog | 002 | must | implemented |
| 009-import-run-reporting | 002-card-catalog | 002 | must | implemented |
| 010-card-search | 002-card-catalog | 003 | must | implemented |
| 011-set-browser | 002-card-catalog | 003 | must | implemented |
| 012-card-detail | 002-card-catalog | 003 | must | implemented |
| **013-add-inventory-item** | 003-inventory-core | 004 | must | implemented |
| 014-edit-inventory-item | 003-inventory-core | 004 | must | implemented |
| 015-remove-inventory-item | 003-inventory-core | 004 | must | implemented |
| **016-fast-add-flow** | 004-collection-experience | 005 | must | implemented |
| 017-set-grid-entry | 004-collection-experience | 005 | must | implemented |
| 018-undo-recent-adds | 004-collection-experience | 005 | should | implemented |
| **019-collection-table** | 004-collection-experience | 006 | must | planned |
| 020-collection-filters | 004-collection-experience | 006 | must | planned |
| 021-saved-views | 004-collection-experience | 006 | should | planned |
| 022-bulk-actions | 004-collection-experience | 006 | must | planned |
| 023-set-completion | 003-inventory-core | 004 | must | implemented |
| 024-missing-cards-view | 004-collection-experience | 006 | must | planned |
| 025-sealed-inventory | 005-sealed-and-wishlist | 007 | must | planned |
| 026-wishlist | 005-sealed-and-wishlist | 007 | should | planned |
| 027-csv-export | 006-import-export | 008 | must | planned |
| **028-csv-import-mapping** | 006-import-export | 008 | must | planned |
| 029-csv-import-commit | 006-import-export | 008 | must | planned |
| 030-profile-settings | 007-profile-and-sharing | 009 | should | planned |
| 031-avatar-upload | 007-profile-and-sharing | 009 | should | planned |
| 032-notification-preferences | 007-profile-and-sharing | 009 | should | planned |
| 033-public-collection | 007-profile-and-sharing | 009 | could | planned |
| 034-admin-catalog-console | 002-card-catalog | 003 | should | implemented |
| 035-account-data-deletion | 007-profile-and-sharing | 009 | should | planned |
| 036-dashboard | 004-collection-experience | 006 | must | planned |

**20 implemented, 16 not started.** The 16 are bolts 006–009 in full: browse, sealed and wishlist,
import/export, profile and sharing. That is the critical path — bolt 006 is what four of intent 002's
open stories wait on.

### What "implemented" leaves open at bolt level

Three of the five built bolts are `partial`, and each on one nameable thing:

| Bolt | Open |
|---|---|
| 001 platform foundation | Nine criteria needing a running platform: JWT `sub` stability across an email change, all seven M2M scopes actually granted, the branding round-trip, console visibility, the logs-api-down path, and the two p95 budgets |
| 002 card catalog | **`FE01.csv` ships with a header and no rows.** ADR-001 rules out scraping the one complete source and fabricating 126 cards would poison a catalog whose job is being correct. Needs hand-compiled data, not code — and until it lands, the catalog is a tested importer over an empty set |
| 003 catalog surface | A full WCAG 2.2 AA pass — contrast, focus visibility, axe — and the three public pages rendered in a browser rather than type-checked |
| 004 inventory core | Nothing. `complete` as of the 2026-08-11 verification run |
| 005 collection entry | The timed session with a real person: median add < 5s, 100 cards < 10min |

Every story has its own file at `units/{unit}/stories/{SSS}-{title-slug}.md`, as
`.specsmd/aidlc/scripts/artifact-validator.cjs` requires — each bolt's `stories:` array is a
cross-reference the validator resolves against these filenames.

**Bold** marks the five carrying the most implementation risk — the importer's idempotency, the
inventory merge invariant under concurrency, the two interactions the product is judged on, and the
import dry run. They have deeper edge-case tables than the rest.

## Intent 002 — price-intelligence

Elaborated 2026-08-15. Bolt numbering continues the global sequence from intent 001.

| Story | Unit | Bolt | Priority | Status |
|---|---|---|---|---|
| 001-harvest-service-skeleton | 001-harvest-service | 010 | must | implemented |
| **002-harvest-schema-and-grants** | 001-harvest-service | 010 | must | implemented |
| 003-celery-redis-runtime | 001-harvest-service | 010 | must | implemented |
| **004-source-registry-and-risk-gate** | 001-harvest-service | 010 | must | implemented |
| 005-run-lifecycle-and-sweeper | 001-harvest-service | 010 | must | implemented |
| 006-rate-limiting-and-identification | 001-harvest-service | 010 | must | implemented |
| 007-source-connector-contract | 002-scrapers | 011 | must | implemented |
| **008-deep-scan** | 002-scrapers | 011 | must | implemented |
| 009-light-scan | 002-scrapers | 011 | must | implemented |
| 010-connector-fixtures-and-drift-detection | 002-scrapers | 011 | must | partial |
| **011-block-detection-and-quarantine** | 002-scrapers | 011 | must | implemented |
| **012-title-to-printing-matcher** | 003-matching-and-observations | 012 | must | implemented |
| 013-condition-extraction | 003-matching-and-observations | 012 | must | implemented |
| 014-observation-store-and-dedupe | 003-matching-and-observations | 012 | must | implemented |
| **015-sold-vs-listed-separation** | 003-matching-and-observations | 012 | must | implemented |
| **023-admin-scope-authorisation** | 005-admin-console | 013 | must | implemented |
| 024-admin-shell-and-routing | 005-admin-console | 013 | must | implemented |
| **025-listing-explorer** | 005-admin-console | 013 | must | implemented |
| 026-run-history-and-health | 005-admin-console | 013 | must | implemented |
| 027-trigger-and-watch-a-scan | 005-admin-console | 013 | must | implemented |
| 016-daily-rollup-job | 004-rollups-and-valuation | 014 | must | implemented |
| 017-outlier-exclusion | 004-rollups-and-valuation | 014 | must | implemented |
| 018-fx-normalisation | 004-rollups-and-valuation | 014 | must | not built |
| **019-price-daily-publication** | 004-rollups-and-valuation | 014 | must | implemented |
| 020-collection-valuation | 004-rollups-and-valuation | 014 | must | implemented |
| 021-portfolio-history-and-pl | 004-rollups-and-valuation | 014 | must | partial |
| 022-nightly-snapshot-valuation | 004-rollups-and-valuation | 014 | must | blocked |
| 028-coverage-and-match-quality | 005-admin-console | 015 | must | implemented |
| 029-price-distribution-and-source-agreement | 005-admin-console | 015 | must | implemented |
| 030-card-price-tab | 006-price-surfaces | 016 | must | implemented |
| 031-market-overview | 006-price-surfaces | 016 | should | implemented |
| 032-portfolio-page | 006-price-surfaces | 016 | must | partial |
| 033-slice-valuation | 006-price-surfaces | 016 | must | blocked |
| 034-price-alerts | 007-alerts | 017 | should | blocked |

### What each unfinished one is waiting for

**018-fx-normalisation is the only one waiting for nobody.** It was recorded as `blocked` and is
not: `fx_rates` and its model exist, and the daily rate fetch and the conversion path were simply
never written. Everything currently rolls up in its observed currency. It can be picked up today,
which is what distinguishes it from the four below.

| Story | Waiting for | Which is |
|---|---|---|
| 021-portfolio-history-and-pl | `collection_snapshots` | phase-1 work planned as insurance for exactly this, and never built |
| 022-nightly-snapshot-valuation | `collection_snapshots` | as above |
| 032-portfolio-page | `collection_snapshots` | as above — current value, coverage and confidence are built; only the series is missing |
| 033-slice-valuation | `/collection`'s filters | intent 001 bolt 006. The story specifies reusing them, and writing a second filter implementation is exactly what it says not to do |
| 034-price-alerts | the notification outbox | intent 001 bolt 009. "An outage delays rather than loses" is an acceptance criterion, not a preference |
| 010-connector-fixtures-and-drift-detection | nothing external | fixtures exist; the drift check over them does not |

So **`collection_snapshots` is the single highest-leverage missing thing in the project**: one table,
written by phase 1, unblocks three phase-2 stories. It was designed a year early precisely so
portfolio history would not start empty on the day phase 2 shipped, and then not built — which is the
one outcome that plan existed to avoid.

**Bold** marks the nine carrying the most risk in intent 002 — the two boundaries that must hold
(grants, `price_daily` publication), the gate that records accepted risk, the discovery scan, the
quarantine that keeps an assertive scraper alive, the matcher and its sold/listed invariant, the
authorisation story, and the explorer that is the whole reason the data is admin-only.

Every story has its own file at `units/{unit}/stories/{SSS}-{title-slug}.md`, as
`.specsmd/aidlc/scripts/artifact-validator.cjs` requires — each bolt's `stories:` array is a
cross-reference the validator resolves against these filenames.

## Counts

By priority:

| | Must | Should | Could | Total |
|---|---|---|---|---|
| Intent 001 | 26 | 9 | 1 | **36** |
| Intent 002 | 32 | 2 | 0 | **34** |
| **Total** | **58** | **11** | **1** | **70** |

By state, as of 2026-08-17:

| | Implemented | Partial | Blocked | Not built | Total |
|---|---|---|---|---|---|
| Intent 001 | 20 | 0 | 0 | 16 | **36** |
| Intent 002 | 27 | 3 | 3 | 1 | **34** |
| **Total** | **47** | **3** | **3** | **17** | **70** |

**67% implemented.** Both remaining clusters are phase-1: intent 001's bolts 006–009, and the three
phase-2 stories that wait on them.

## Intents not yet decomposed to stories

| Intent | Units | Stories | Status |
|---|---|---|---|
| 003-marketplace | 6 | 21 (enumerated in `units.md`) | outline only — commercial model undecided |
| 004-card-scanning | — | — | inception, blocked at Checkpoint 1 on four unanswered questions. Requirements drafted (490 lines); no system context, units, stories or bolt plan |
