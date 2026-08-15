---
created: 2026-08-09T12:00:00Z
updated: 2026-08-09T12:00:00Z
---

# Coding Standards

**Critical context for the Construction Agent.** Code it generates must conform.

## Inheritance

This project is a client of the platform in `../auth` and **inherits that repo's canonical rules**:
`../auth/docs/conventions/standards.md`. Where this file is silent, that file governs. What follows
is the subset that matters here plus our deltas.

Inherited without change:

- Error shape, always — never a bare `detail` string from business logic:
  ```json
  { "error": { "code": "printing_not_found", "message": "Printing not found", "details": {} } }
  ```
- Status codes: `200` read · `201` create · `204` delete · `400` validation · `404` not found ·
  `409` conflict. `PATCH` with `model_dump(exclude_unset=True)` for partial, `PUT` for replacement.
- Public IDs are UUIDs. Never expose an auto-increment integer in a response.
- Query strings are never logged.
- Never log authorization headers, tokens, secrets, or any value matching a sensitive key pattern.
- MySQL everywhere; per-service Alembic owns the schema; `create_all` is the **unit-test** path only
  and must never be described as the production migration mechanism.
- Native `JSON` columns for genuinely flexible config — do not flatten them into typed columns.
- Models extend the shared UUID-primary-key and timestamp mixins.

## Naming

| Context | Convention | Example |
|---|---|---|
| Python identifiers | `snake_case` | `inventory_service`, `add_item` |
| Python classes | `PascalCase` | `InventoryService`, `CatalogImporter` |
| TypeScript identifiers | `camelCase` | `selectedPrintingId`, `listInventory` |
| TypeScript types | `PascalCase` | `InventoryItem`, `ElementKey` |
| React components | `PascalCase`, one per file | `CardRow.tsx` |
| React hooks | `useThing` | `useInventory`, `useAddSession` |
| Tables / columns | `snake_case` | `inventory_items`, `acquired_unit_price_cents` |
| Log component | `kebab-case` | `catalog-importer`, `inventory-write` |
| Log operation | `kebab-case` | `add`, `bulk-import`, `recompute-completion` |
| Feature usage keys | `dot.separated` | `inventory.item_added` |
| Migration files | `NNNN_snake_case` | `0003_add_inventory_items` |

## Deltas specific to this project

These exist because of decisions taken at inception. They are not stylistic.

1. **Ownership is a signature, not a filter.** Every user-scoped repository method takes
   `user_sub: str` as its **first positional argument**. An unscoped query must be impossible to
   write, not merely discouraged in review.
   ```python
   def list_items(self, user_sub: str, *, filters: InventoryFilters) -> Page[InventoryItem]: ...
   ```
   `user_sub` always originates from the validated JWT. There is no code path where it is read from
   a request body, query parameter or header.

2. **Unauthorised access to a real row returns `404`, never `403`.** A `403` confirms the row
   exists, which is itself a leak.

3. **Money is `*_cents BIGINT` plus an explicit `currency CHAR(3)`.** Never a float, never an
   implied currency. A bare number is not money and must be rejected at the boundary.

4. **All timestamps are `DATETIME(6)` UTC.** Naive local datetimes are a bug.

5. **`log_event()` is the only way anything writes a log.** Direct writes to `app_logs`, and direct
   `logs.write` calls, are a review failure — the two-destination routing rule lives in exactly one
   function so it can be changed once.

6. **Best-effort calls can never fail a request.** Platform logging, forwarding and usage metering
   are wrapped so an exception is swallowed and counted, never propagated.

7. **Domain colour tokens are constants.** Element and rarity values live in `theme/domain.ts` and
   are never sourced from branding. Chrome tokens come from branding-api. Mixing the two layers is a
   review failure.

8. **No monetary figure renders without its confidence.** From phase 2, the money component takes
   `confidence` as a **required** prop. A number without provenance is not shippable.

## Layering (backend, non-negotiable)

```
Controllers → Services → Repositories → SQLAlchemy models → MySQL
```

- Controllers are thin routers with an explicit `/api/v1` prefix, no DB access, no business logic.
- Services hold business logic and never touch a session directly.
- Repositories are the only place that touches the DB.
- Dependency wiring lives in `app/core/dependencies.py`. New service wires go there, not into
  module-level singletons.

Crossing a layer — a controller importing a repository, a service opening a session — is a review
failure regardless of how convenient it is.

## Frontend

- TypeScript `strict`. No `any` in committed code; `unknown` plus a narrowing guard instead.
- Server state is TanStack Query. Client state is React context. No Redux — the domain state is
  server state and duplicating it into a store is where staleness bugs come from.
- Zod schemas are shared between form validation and API response parsing, so a backend shape change
  fails loudly rather than rendering `undefined`.
- Optimistic mutations use `onMutate`/`onError` rollback and **revert visibly**. A silent revert
  teaches users not to trust the UI.
- Filter state serialises into the URL.
- No `outline: none` without a replacement focus style, ever.

## Formatting

| | |
|---|---|
| Python | `ruff format` + `ruff check`, line length 100 |
| TypeScript | Prettier, 2 spaces, single quotes, line length 100 |
| Import order | stdlib → third-party → first-party → relative |
| Line endings | LF, enforced by `.gitattributes` |

## Comments

Explain **why**, never **what**. A comment restating the code is noise that goes stale. Comments
earn their place when they record a non-obvious constraint:

```python
# Upsert, not read-then-write: the fast-add flow fires concurrent requests by design,
# and read-then-write passes every sequential test while losing rows in production.
```

Match the surrounding file's comment density. Do not add a docstring to a three-line function that
says what its name already says.

## Testing

- `pytest` + `pytest-asyncio`. Unit tests against in-memory SQLite via `create_all`; integration
  tests against MySQL.
- Coverage > 80% per bolt, but coverage is a floor, not a goal.
- **Every user-scoped endpoint has an explicit test asserting cross-user access is impossible.** Not
  a sampled subset — every one.
- Concurrency-sensitive invariants are tested **under real concurrency**, not sequentially. The
  merge-on-duplicate rule is the standing example: a sequential test passes on a broken
  implementation.
- Frontend: component tests pin interaction contracts (the add flow's keyboard behaviour), not
  implementation details.
- Fixtures for the awkward real-world inputs: UTF-8-BOM, CP1252, semicolon-delimited CSV.

## Definition of done

- [ ] Acceptance criteria met, and demonstrated
- [ ] Layering respected
- [ ] Cross-user access test present for any new user-scoped endpoint
- [ ] `ruff` and Prettier clean
- [ ] Coverage > 80%
- [ ] No secret reachable from the browser, no secret in a log line
- [ ] Any structural decision recorded in `standards/decision-index.md`
