---
id: 002-harvest-schema-and-grants
unit: 001-harvest-service
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 010-harvest-service-foundation
implemented: false
---

# Story: 002-harvest-schema-and-grants

## User Story

**As an** operator
**I want** the two services to be unable to write each other's data
**So that** the isolation between them is a property of the database rather than a promise in a
document

## Acceptance Criteria

- [ ] **Given** the migrations, **When** `harvest-api` runs `alembic upgrade head`, **Then** the
      `elestrals_harvest` schema is created with its own version table, independent of `elestrals`
- [ ] **Given** the `harvest-api` MySQL user, **When** it attempts any `INSERT`, `UPDATE` or
      `DELETE` against any table in `elestrals`, **Then** MySQL refuses it
- [ ] **Given** the `elestrals-api` MySQL user, **When** it attempts any write against any table in
      `elestrals_harvest`, **Then** MySQL refuses it
- [ ] **Given** the `harvest-api` user, **When** it reads `elestrals.printings`, `cards`, `sets` or
      `sealed_products`, **Then** it succeeds — the matcher needs them
- [ ] **Given** the `harvest-api` user, **When** it reads `elestrals.inventory_items` or
      `user_profiles`, **Then** it is refused. The harvester has no business knowing who owns what
- [ ] **Given** a test suite, **When** it runs against a real MySQL, **Then** there is a test that
      *attempts* each forbidden write and asserts the refusal

## Technical Notes

Two users, granted narrowly:

```sql
-- harvest-api
GRANT ALL PRIVILEGES ON elestrals_harvest.* TO 'elestrals_harvest'@'%';
GRANT SELECT ON elestrals.sets            TO 'elestrals_harvest'@'%';
GRANT SELECT ON elestrals.cards           TO 'elestrals_harvest'@'%';
GRANT SELECT ON elestrals.printings       TO 'elestrals_harvest'@'%';
GRANT SELECT ON elestrals.sealed_products TO 'elestrals_harvest'@'%';

-- elestrals-api: the read on price_daily is granted in story 019, not here
```

Table-level grants rather than schema-level, deliberately: `GRANT SELECT ON elestrals.*` would hand
the harvester every user's inventory the moment somebody adds a table.

Two Alembic trees, two `alembic.ini`, two version tables. Neither service migrates the other's
schema, and neither release job runs the other's migrations.

The negative tests belong in the MySQL integration suite (`scripts/verify_mysql.py` already
establishes that path), not the SQLite unit suite — SQLite has no grants, so a boundary asserted
there would assert nothing.

## Dependencies

### Requires
- 001-harvest-service-skeleton

### Enables
- 004-source-registry-and-risk-gate
- 019-price-daily-publication — which adds the one grant in the other direction

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Local development with one root user | Allowed, but the MySQL integration test must run against the real two-user setup before release, or the boundary is untested |
| A new phase-1 table appears | Nothing changes — table-level grants mean the harvester does not silently gain access |
| The matcher needs a new catalog table | A new explicit grant, added deliberately, in a migration |
| Someone grants `elestrals.*` for convenience | Review failure. The narrowness is the feature |

## Out of Scope

- `price_daily`'s grant in the other direction (story 019)
- Any table beyond `price_sources` and `harvest_runs` (later stories create their own)
