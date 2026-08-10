---
intent: 001-collection-tracker
phase: inception
status: units-decomposed
updated: 2026-08-09T12:00:00Z
---

# Collection Tracker - Unit Decomposition

This intent decomposes into **7 units**, 35 stories.

The decomposition follows the dependency of *data before behaviour before surface*: the platform
wiring must exist before anything, the catalog must exist before inventory can point at it, and
inventory must exist before there is anything to browse, complete or export.

---

### Unit 001: platform-foundation

**Description**: Fork `../app-starter`, stand up the `elestrals` database and Alembic tree, wire the
M2M service account, and put our own logging and usage metering in place. Nothing domain-specific —
this is the floor everything else stands on.

**Stories**:
- 001-sign-in-with-platform
- 002-app-shell-and-routing
- 003-branding-driven-theme
- 004-app-logging
- 005-platform-log-forwarding
- 006-usage-metering

**Deliverables**:
- `frontend/` and `backend/` forked from app-starter, renamed, building and running
- `elestrals` database created, Alembic initialised, `app_logs` + `user_profiles` migrated
- `log_event()` helper with redaction and conditional forwarding
- `usage_track()` helper
- M2M service account provisioned with all seven scopes, verified by a smoke test
- App shell: rail, top bar, routing, EN/NL, theme from branding, error boundary, "platform down" screen

**Dependencies**: Depends on nothing. Depended by every other unit.

**Estimated Complexity**: M

---

### Unit 002: card-catalog

**Description**: The canonical Elestrals catalog — schema, a re-runnable importer that normalises
public sources into it, search and browse APIs, and the operator console over import health. This is
the unit with real unknowns in it, which is why it comes second and starts with a spike.

**Stories**:
- 007-catalog-schema
- 008-catalog-importer
- 009-import-run-reporting
- 010-card-search
- 011-set-browser
- 012-card-detail
- 034-admin-catalog-console

**Deliverables**:
- `sets` / `cards` / `printings` / `sealed_products` / `catalog_imports` migrations
- `importer/` with a per-source adapter, a normaliser and an idempotent upsert
- `GET /api/v1/cards`, `/cards/{id}`, `/sets`, `/sets/{code}` with filters and prefix search
- `/sets`, `/sets/:code`, `/cards/:id` pages
- `/admin/catalog` operator console

**Dependencies**:
- Depends on: 001
- Depended by: 003, 004, 005, 006

**Estimated Complexity**: L — the importer carries the intent's largest unknown

---

### Unit 003: inventory-core

**Description**: The domain heart. Owning a printing in a condition, in a quantity, with a cost
basis. Ownership rules, the merge-on-duplicate invariant, and the completion projection.

**Stories**:
- 013-add-inventory-item
- 014-edit-inventory-item
- 015-remove-inventory-item
- 023-set-completion

**Deliverables**:
- `inventory_items` + `set_completion` migrations
- `InventoryService` enforcing merge-on-duplicate, graded-copies-are-separate, `quantity > 0`
- Repository layer where every method takes `user_sub` as its first argument — ownership is not
  optional at the type level
- `POST/PATCH/DELETE /api/v1/inventory`, `GET /api/v1/inventory`, `GET /api/v1/completion`
- Completion recomputed on write, not on read

**Dependencies**:
- Depends on: 001, 002
- Depended by: 004, 005, 006

**Estimated Complexity**: M

---

### Unit 004: collection-experience

**Description**: Everything the collector actually touches — the table, the filters, and the two
entry flows that decide whether the product survives contact with a 400-card box.

**Stories**:
- 016-fast-add-flow
- 017-set-grid-entry
- 018-undo-recent-adds
- 019-collection-table
- 020-collection-filters
- 021-saved-views
- 022-bulk-actions
- 024-missing-cards-view
- 036-dashboard

**Deliverables**:
- `/collection` virtualized table with filter rail, density toggle, saved views, bulk actions
- `/collection/add` keyboard-first flow with carry-forward and session tally
- `/collection/add/set/:setCode` grid mode
- `/dashboard` with stat tiles, completion rings and recent activity
- Optimistic mutation layer with visible revert
- `saved_views` migration

**Dependencies**:
- Depends on: 002, 003
- Depended by: none

**Estimated Complexity**: L — the highest UX risk in the intent

---

### Unit 005: sealed-and-wishlist

**Description**: The two adjacent inventories: sealed product, which must never contaminate
singles maths, and the wishlist, which is the inverse of inventory and the seed for phase-2 alerts.

**Stories**:
- 025-sealed-inventory
- 026-wishlist

**Deliverables**:
- `sealed_inventory_items` + `wishlist_items` migrations
- `/sealed` and `/wishlist` pages
- Explicit "open a sealed product" action that does **not** auto-generate singles

**Dependencies**:
- Depends on: 002, 003
- Depended by: 006 (export covers both)

**Estimated Complexity**: S

---

### Unit 006: import-export

**Description**: Get a collection in from a spreadsheet, and get it back out. The anti-lock-in unit,
and the one that makes the product adoptable by someone who already tracks in Excel.

**Stories**:
- 027-csv-export
- 028-csv-import-mapping
- 029-csv-import-commit

**Deliverables**:
- `GET /api/v1/export` honouring the active filter, covering singles, sealed and wishlist
- Two-step import: upload + column mapping + **dry-run diff**, then an atomic commit
- Matching strategy: exact printing id → set+number+finish → fuzzy name with a confirmation step
- CSV-injection neutralisation on export; untrusted-input handling on import
- `/import-export` page

**Dependencies**:
- Depends on: 003, 005
- Depended by: none

**Estimated Complexity**: M — the matcher is deceptively hard

---

### Unit 007: profile-and-sharing

**Description**: The account surface — app-owned preferences over platform-owned identity,
notification channels, optional public sharing, and the data-deletion path.

**Stories**:
- 030-profile-settings
- 031-avatar-upload
- 032-notification-preferences
- 033-public-collection
- 035-account-data-deletion

**Deliverables**:
- `/settings/profile`, `/settings/notifications`
- `notification_preferences` + `notification_outbox` migrations, with the retrying outbox worker
- `/u/:handle` public view with a strict projection that cannot leak cost basis
- Deletion job with re-authentication and a 30-day guarantee

**Dependencies**:
- Depends on: 001, 003
- Depended by: none

**Estimated Complexity**: M

---

## Unit Dependency Graph

```text
                          [001 platform-foundation]
                                     │
                          [002 card-catalog]
                                     │
                          [003 inventory-core]
                    ┌────────────────┼────────────────┐
                    │                │                │
        [004 collection-experience]  │      [007 profile-and-sharing]
                                     │
                         [005 sealed-and-wishlist]
                                     │
                          [006 import-export]
```

Only 001 → 002 → 003 is a genuine serial chain. After 003 lands, 004, 005 and 007 are independent
and could run in parallel if there were more than one pair of hands.

## Execution Order

| Order | Unit | Why here |
|---|---|---|
| 1 | 001 platform-foundation | Nothing compiles without it |
| 2 | 002 card-catalog | Contains the intent's biggest unknown — de-risk it early, while there is still room to change course |
| 3 | 003 inventory-core | The domain invariants; everything downstream assumes them |
| 4 | 004 collection-experience | The product becomes usable here. First point at which it is worth showing anyone |
| 5 | 005 sealed-and-wishlist | Small, additive, low risk |
| 6 | 006 import-export | Needs 003 and 005 complete to export a full picture |
| 7 | 007 profile-and-sharing | Genuinely last — nothing depends on it, and public sharing should not exist before the data model has settled |

**Deliberate ordering choice:** unit 002 is scheduled before 003 even though 003 is more central,
because 002 is where this intent can fail. If public Elestrals card data turns out to be
unobtainable at usable fidelity, that must surface in week one — not after the inventory UI is
built on top of an assumption.
