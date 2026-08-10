---
intent: 001-collection-tracker
phase: inception
status: construction
created: '2026-08-09T12:00:00Z'
updated: '2026-08-09T12:00:00Z'
---

# Requirements: Collection Tracker

## Intent Overview

Let a signed-in collector record and manage everything they own of the Elestrals TCG — individual
cards at printing-and-condition precision, and sealed product — and see meaningful structure over
it: set completion, what is missing, and what they still want. This intent also stands up the whole
application: the fork of `app-starter`, the `elestrals` database, our own logging, platform
integration and the card catalog that phases 2 and 3 both depend on.

Nothing in this intent needs a price. Valuation is intent 002.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Bulk entry is not painful | 100 cards entered in < 10 min; median single-add interaction < 5s | Must |
| Collection structure is visible | Set completion correct for 100% of released sets | Must |
| The catalog stays current | A new set is importable within 24h of data being published, with no code change | Must |
| Users are not locked in | Full CSV export of everything a user has entered | Must |
| The app is observable from day one | 100% of requests in `app_logs`; errors and security events visible in the platform console | Must |
| Users can leave with dignity | Account deletion removes all app-owned rows within 30 days | Should |

---

## Functional Requirements

### FR-1: Sign in with the platform
- **Description**: Users authenticate exclusively through the platform's login-api using
  Authorization Code + PKCE, via the embedded `<LoginForm>`. No credential is ever handled by this
  app.
- **Acceptance Criteria**: An unauthenticated visit to any `A` route renders the login gate; after
  sign-in the user lands on the originally requested route; the access token is never written to
  `localStorage`; a tampered `redirect_uri` is rejected by the platform.
- **Priority**: Must
- **Related Stories**: 001-sign-in-with-platform, 002-app-shell-and-routing

### FR-2: Theme the app from platform branding
- **Description**: The entire application — not only the login form — is themed from the resolved
  branding for our project, via branding-api's anonymous `/resolve`.
- **Acceptance Criteria**: Changing the project's primary colour in the platform console and
  reloading changes the app's chrome; element and rarity colours are unchanged; if branding-api is
  unreachable the built-in default theme renders and the app is fully usable.
- **Priority**: Must
- **Related Stories**: 003-branding-driven-theme

### FR-3: Our own logging table, with platform forwarding
- **Description**: Every request and notable domain event is written to `elestrals.app_logs`. Rows
  of level `error`/`critical`, and every event in the `security` category, are additionally
  forwarded to the platform's logs-api through the backend's M2M account.
- **Acceptance Criteria**: A request produces exactly one `app_logs` row with method, route,
  status, duration and `request_id`; an unhandled exception produces a `critical` row with a trace
  and appears in the platform console; `Authorization` headers and any key matching a secret
  pattern are redacted before persistence; logs-api being down never fails a user request.
- **Priority**: Must
- **Related Stories**: 004-app-logging, 005-platform-log-forwarding

### FR-4: Meter feature usage to the platform
- **Description**: Product usage is recorded through logs-api's feature-usage stream so the
  platform console reports real behaviour.
- **Acceptance Criteria**: Adding inventory records `inventory.item_added` with the user as subject,
  the quantity added, and the set code as `reference_1`; the console's Feature usage view shows the
  counts; metering failure never fails the originating request.
- **Priority**: Must
- **Related Stories**: 006-usage-metering

### FR-5: Import the card catalog
- **Description**: A re-runnable importer populates `sets`, `cards`, `printings` and
  `sealed_products` from configured external sources, normalising to our canonical model.
- **Acceptance Criteria**: Running the importer twice over unchanged sources produces zero
  additional rows and zero updates; a new set appears with all its printings; every run writes a
  `catalog_imports` row with counts; rows that fail normalisation are rejected with a reason and
  never partially written; the run is idempotent per `(set, collector_number, rarity, finish,
  language, edition)`.
- **Priority**: Must
- **Related Stories**: 007-catalog-schema, 008-catalog-importer, 009-import-run-reporting

### FR-6: Search and browse the catalog
- **Description**: Anyone, signed in or not, can search cards by name and browse by set, element,
  rarity and card type.
- **Acceptance Criteria**: A 3-character prefix returns ranked matches in < 150ms p95; results
  show set, collector number, element and rarity; filters combine; a card detail page shows every
  printing of that card.
- **Priority**: Must
- **Related Stories**: 010-card-search, 011-set-browser, 012-card-detail

### FR-7: Record owned singles
- **Description**: A user adds, edits and removes inventory at printing + condition precision, with
  quantity, optional cost basis, acquisition date, storage location, grading and notes.
- **Acceptance Criteria**: Adding a printing+condition that already exists increments quantity
  rather than creating a second row; graded copies are always separate rows; quantity cannot go
  below 1 (removal is explicit); all writes are scoped to the caller's `sub` and a crafted request
  cannot touch another user's row; edits are optimistic in the UI and revert visibly on failure.
- **Priority**: Must
- **Related Stories**: 013-add-inventory-item, 014-edit-inventory-item, 015-remove-inventory-item

### FR-8: Fast bulk entry
- **Description**: A keyboard-first add flow and a whole-set grid mode for entering a large lot.
- **Acceptance Criteria**: In the add flow, `type → arrow → Enter` saves and re-focuses the search
  field with condition and finish preserved from the previous add; a session tally shows what was
  added; the last 20 adds can be undone individually; in grid mode a click is +1 and shift-click
  is −1 with no page reload.
- **Priority**: Must
- **Related Stories**: 016-fast-add-flow, 017-set-grid-entry, 018-undo-recent-adds

### FR-9: Browse and filter the collection
- **Description**: A virtualized table of everything owned, filterable and sortable, with saved
  views and a density toggle.
- **Acceptance Criteria**: 10,000 rows scroll at 60fps; filters on set, element, rarity, condition,
  finish, language, graded and for-trade combine; sort by name, set, quantity, recently added; a
  named view persists per user and restores its filters; bulk-select supports edit, delete and
  export.
- **Priority**: Must
- **Related Stories**: 019-collection-table, 020-collection-filters, 021-saved-views, 022-bulk-actions

### FR-10: Set completion
- **Description**: For every set, show how much of it the user owns, and which printings are
  missing.
- **Acceptance Criteria**: Completion is `distinct owned printings in set / set.card_count`,
  recomputed on every inventory write; the set detail page toggles owned/missing/all; the missing
  list is exportable to CSV.
- **Priority**: Must
- **Related Stories**: 023-set-completion, 024-missing-cards-view

### FR-11: Sealed product inventory
- **Description**: Track packs, boxes, decks and bundles separately from singles, including whether
  a product is still sealed.
- **Acceptance Criteria**: Sealed items never appear in singles views or in completion maths;
  marking a box as opened does not create singles automatically (that is an explicit action the
  user takes later).
- **Priority**: Must
- **Related Stories**: 025-sealed-inventory

### FR-12: Wishlist
- **Description**: Track wanted printings with desired quantity, an optional maximum price and a
  priority.
- **Acceptance Criteria**: A printing appears at most once per user; acquiring it prompts to remove
  it from the wishlist; the wishlist is exportable.
- **Priority**: Should
- **Related Stories**: 026-wishlist

### FR-13: CSV import and export
- **Description**: Import an existing collection from CSV and export everything owned.
- **Acceptance Criteria**: The importer presents a column mapper and a **dry-run diff** (rows to
  add, update, reject with reasons) that the user must confirm before anything is written; an
  import is atomic — it fully applies or fully rolls back; export honours the current filter and
  round-trips back through import without loss.
- **Priority**: Must
- **Related Stories**: 027-csv-export, 028-csv-import-mapping, 029-csv-import-commit

### FR-14: Profile and preferences
- **Description**: A settings area showing platform-enriched identity plus app-owned preferences.
- **Acceptance Criteria**: Email and display name come from auth-api and are read-only here (they
  are edited in the platform's `/account`); handle, collection visibility, default currency and
  condition scale are editable and persist; an avatar uploads through storage-api as an `owned`
  file.
- **Priority**: Should
- **Related Stories**: 030-profile-settings, 031-avatar-upload

### FR-15: Notification preferences
- **Description**: Per-event-type channel preferences, delivered through notification-api.
- **Acceptance Criteria**: Preferences persist per user; a test send reaches the chosen channel; a
  notification-api outage queues in `notification_outbox` and retries rather than dropping.
- **Priority**: Should
- **Related Stories**: 032-notification-preferences

### FR-16: Public collection sharing
- **Description**: A user may expose their collection read-only at `/u/:handle`.
- **Acceptance Criteria**: Default visibility is `private`; `link` requires an unguessable token;
  `public` is indexable by handle; **cost basis, acquisition price, storage location and notes are
  never exposed at any visibility level**.
- **Priority**: Could
- **Related Stories**: 033-public-collection

### FR-17: Operator catalog console
- **Description**: An RBAC-gated view of import runs and catalog health.
- **Acceptance Criteria**: Shows last run per source with counts and duration, sets whose data is
  older than 30 days, and rejected rows with reasons; a non-privileged user gets 403.
- **Priority**: Should
- **Related Stories**: 034-admin-catalog-console

### FR-18: Account data deletion
- **Description**: A user can request deletion of everything this app holds about them.
- **Acceptance Criteria**: Request is confirmed by re-authentication; all rows keyed on the user's
  `sub` are removed within 30 days; an audit row recording that a deletion occurred is retained
  without personal data; the platform account itself is closed through the platform's own
  `/account`, not here.
- **Priority**: Should
- **Related Stories**: 035-account-data-deletion

---

## Non-Functional Requirements

### Performance
| Requirement | Metric | Target |
|---|---|---|
| Card search | p95 latency | < 150ms |
| Collection list, 10k rows | p95 API latency | < 400ms |
| Collection list scroll | frame rate | 60fps sustained |
| Inventory write | p95 latency | < 200ms |
| Set completion recompute | p95 | < 100ms |
| First contentful paint, warm cache | p75 | < 1.5s |

### Scalability
| Requirement | Metric | Target (12-month) |
|---|---|---|
| Registered users | accounts | 20,000 |
| Inventory rows | rows | 10M |
| Catalog printings | rows | 50,000 |
| Concurrent sessions | active | 500 |

### Security
| Requirement | Standard | Notes |
|---|---|---|
| Authentication | OAuth 2.0 Authorization Code + PKCE | login-api is the only issuer; no local credentials |
| Token validation | JWKS, `RS256` only, `iss` pinned | locally, cached, single-flight |
| Authorization | ownership by JWT `sub` | every user-scoped repository method filters on `user_sub`; ids from the client are never trusted |
| Operator routes | platform RBAC | 403 on valid token without permission, 401 without one |
| Secrets | server-side only | M2M secret never reaches the browser; redacted before any log write |
| Transport | TLS 1.2+ | enforced at the proxy |
| Input | Pydantic v2 at the boundary | parameterised SQL only; CSV import treated as untrusted, formula-injection prefixes neutralised on export |
| Rate limiting | per-user and per-IP | 60 writes/min/user, 600 reads/min/user |

### Reliability
| Requirement | Metric | Target |
|---|---|---|
| Availability | uptime | 99.5% |
| Recovery | RTO | < 4 hours |
| Data loss | RPO | < 24 hours (nightly dump + binlog) |
| Degradation | platform module outage | reduced feature, never an outage — see `system-architecture.md` |

### Compliance
| Requirement | Standard | Notes |
|---|---|---|
| Personal data | GDPR | we store `sub` and app preferences only; identity stays in the platform. Export and deletion are FR-13 and FR-18 |
| Accessibility | WCAG 2.2 AA | binding — see `ux-guide.md` §9 |
| Intellectual property | publisher trademark & card art | unofficial-status notice on every page; card images referenced by URL, not hosted, until written permission exists |

---

## Constraints

### Technical Constraints

**Project-wide standards**: `standards/tech-stack.md`, `standards/system-architecture.md`,
`standards/data-model.md`, `standards/ux-guide.md`.

**Intent-specific:**
- The fork of `../app-starter` must keep its `security.py`, `admin.py` and `project_logger.py`
  patterns intact — divergence there breaks the shared platform conventions.
- Our Alembic tree is ours alone; we never write to `alembic_tenant` or any platform database.
- The frontend may hold only a public `client_id`. Any feature needing M2M goes through our backend.
- Element and rarity colours are domain constants and must not be sourced from branding.

### Business Constraints
- Single developer plus AI assistance — bolts are sized to be individually completable.
- No budget for licensed card data in phase 1; the importer targets public sources.
- The publisher relationship is unmanaged. Anything that looks official is out of bounds.

---

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|---|---|---|
| Card data is obtainable from public sources at usable fidelity | Phase 1 has no catalog and the whole product stalls | Spike the importer against one real set **first**, in bolt 002, before building anything on top of it; CSV seed is the fallback |
| The platform is deployed and reachable in every environment we target | No sign-in, no app | Local dev runs the platform's `docker-compose.yml`; the app has a documented "platform down" screen |
| An M2M service account with the listed scopes can be provisioned | Enrichment, logging, usage and notifications all fail | Provision it in bolt 001 and fail the bolt if not; each dependent feature has a flag (`ENABLE_*`) so the app runs without it |
| Collectors will accept printing-level precision rather than just card names | Data entry feels heavy and users churn | The add flow defaults to the most common printing and carries condition/finish forward; precision is available, not mandatory |
| A user's collection fits comfortably in one MySQL instance | Rewrite of the data layer | 10M rows is unremarkable for MySQL 8; revisit only on measurement |
| Card art may be hot-linked in the interim | Broken images, or a complaint | Store URLs not bytes; a single config switch moves to storage-api once permission exists |

---

## Open Questions

| Question | Owner | Due | Resolution |
|---|---|---|---|
| Which public source has the most complete Elestrals card data, and what are its terms? | Lars | before bolt 002 | **Pending** — resolved by the bolt-002 spike |
| Do we have, or can we get, written permission to display card art? | Lars | before public launch | **Pending** — URL-referencing until then |
| Product name — "Elestral Vault" or something further from the trademark? | Lars | before public launch | **Pending** |
| Which condition vocabulary is primary, TCGplayer or Cardmarket? | Lars | before bolt 003 | Both stored; `user_profiles.condition_scale` chooses the display. **Resolved** |
| Does the platform's `sub` remain stable across a user's email change? | Lars | before bolt 001 | Assumed yes (it is an account id, not an email). **Verify in bolt 001** — everything we own is keyed on it |
