---
updated: 2026-08-09T12:00:00Z
mode: single-file
---

# Story Index

Project-wide story tracking. 36 stories across intent 001, all `planned`.

Intents 002 and 003 are decomposed to unit level; their stories are enumerated in their respective
`units.md` and are elaborated when that intent enters construction.

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

## Counts

| | Must | Should | Could | Total |
|---|---|---|---|---|
| Intent 001 | 26 | 9 | 1 | **36** |

## Intents 002 and 003

| Intent | Units | Stories | Status |
|---|---|---|---|
| 002-price-intelligence | 6 | 24 (enumerated in `units.md`) | decomposed, not elaborated |
| 003-marketplace | 6 | 21 (enumerated in `units.md`) | outline only — commercial model undecided |
