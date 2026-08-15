---
updated: 2026-08-15T16:30:00Z
mode: single-file
---

# Story Index

Project-wide story tracking. **70 stories** — 36 in intent 001 (all `planned`), 34 in intent 002.

Intent 002 was elaborated on 2026-08-15, when ADR-004 (scrape rather than licence) and the
second-backend decision took it into construction, and **built the same day** — 27 of its 34
stories are implemented, 3 partial and 4 blocked on phase-1 work that has not shipped
(`collection_snapshots`, `/collection`, the outbox). Intent 001's own stories are still `planned`:
bolts 005-009 have not been built, which is what blocks the four.

Intent 003 remains decomposed to unit level only; its stories are enumerated in its `units.md`.

## Intent 001 — collection-tracker

| Story | Unit | Bolt | Priority | Status |
|---|---|---|---|---|
| 001-sign-in-with-platform | 001-platform-foundation | 001 | must | planned |
| 002-app-shell-and-routing | 001-platform-foundation | 001 | must | planned |
| 003-branding-driven-theme | 001-platform-foundation | 001 | must | planned |
| 004-app-logging | 001-platform-foundation | 001 | must | planned |
| 005-platform-log-forwarding | 001-platform-foundation | 001 | must | planned |
| 006-usage-metering | 001-platform-foundation | 001 | must | planned |
| 007-catalog-schema | 002-card-catalog | 002 | must | planned |
| **008-catalog-importer** | 002-card-catalog | 002 | must | planned |
| 009-import-run-reporting | 002-card-catalog | 002 | must | planned |
| 010-card-search | 002-card-catalog | 003 | must | planned |
| 011-set-browser | 002-card-catalog | 003 | must | planned |
| 012-card-detail | 002-card-catalog | 003 | must | planned |
| **013-add-inventory-item** | 003-inventory-core | 004 | must | planned |
| 014-edit-inventory-item | 003-inventory-core | 004 | must | planned |
| 015-remove-inventory-item | 003-inventory-core | 004 | must | planned |
| **016-fast-add-flow** | 004-collection-experience | 005 | must | planned |
| 017-set-grid-entry | 004-collection-experience | 005 | must | planned |
| 018-undo-recent-adds | 004-collection-experience | 005 | should | planned |
| **019-collection-table** | 004-collection-experience | 006 | must | planned |
| 020-collection-filters | 004-collection-experience | 006 | must | planned |
| 021-saved-views | 004-collection-experience | 006 | should | planned |
| 022-bulk-actions | 004-collection-experience | 006 | must | planned |
| 023-set-completion | 003-inventory-core | 004 | must | planned |
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
| 034-admin-catalog-console | 002-card-catalog | 003 | should | planned |
| 035-account-data-deletion | 007-profile-and-sharing | 009 | should | planned |
| 036-dashboard | 004-collection-experience | 006 | must | planned |

Every story has its own file at `units/{unit}/stories/{SSS}-{title-slug}.md`, as
`.specsmd/aidlc/scripts/artifact-validator.cjs` requires — each bolt's `stories:` array is a
cross-reference the validator resolves against these filenames.

**Bold** marks the five carrying the most implementation risk — the importer's idempotency, the
inventory merge invariant under concurrency, the two interactions the product is judged on, and the
import dry run. They have deeper edge-case tables than the rest.

Validation status: `artifact-validator.cjs` → **0 issues**; `status-integrity.cjs` → **0
inconsistencies**.

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
| 018-fx-normalisation | 004-rollups-and-valuation | 014 | must | blocked |
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

**Bold** marks the nine carrying the most risk in intent 002 — the two boundaries that must hold
(grants, `price_daily` publication), the gate that records accepted risk, the discovery scan, the
quarantine that keeps an assertive scraper alive, the matcher and its sold/listed invariant, the
authorisation story, and the explorer that is the whole reason the data is admin-only.

Every story has its own file at `units/{unit}/stories/{SSS}-{title-slug}.md`, as
`.specsmd/aidlc/scripts/artifact-validator.cjs` requires — each bolt's `stories:` array is a
cross-reference the validator resolves against these filenames.

## Counts

| | Must | Should | Could | Total |
|---|---|---|---|---|
| Intent 001 | 26 | 9 | 1 | **36** |
| Intent 002 | 32 | 2 | 0 | **34** |
| **Total** | **58** | **11** | **1** | **70** |

## Intent 003

| Intent | Units | Stories | Status |
|---|---|---|---|
| 003-marketplace | 6 | 21 (enumerated in `units.md`) | outline only — commercial model undecided |
