---
created: 2026-08-09T12:00:00Z
updated: 2026-08-09T12:00:00Z
---

# API Conventions

Our backend is `/api/v1` on `:9000`. It is **not** a platform module service — it does not take a
platform prefix from the service registry, and it is not an M2M resource server. It is one app's
backend, consumed by one frontend.

## Shape

| | |
|---|---|
| Prefix | `/api/v1` |
| Auth | `Authorization: Bearer <access token>`, JWKS-validated locally, `RS256`, `iss` pinned |
| Identity | the JWT `sub`, and nothing else |
| Content | `application/json`; CSV endpoints stream `text/csv` |
| IDs | UUIDs in every response |
| Money | `{ "amount_cents": 4850, "currency": "EUR" }` — never a bare number, never a float |
| Times | ISO 8601 UTC with `Z` |

## Endpoints (phase 1)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/health` | — | liveness, polled by status-api |
| `GET` | `/api/v1/me` | user | profile, enriched from auth-api |
| `PATCH` | `/api/v1/me` | user | app preferences |
| `POST` | `/api/v1/events` | user | relay a client event into logging, stamped with the validated caller |
| `GET` | `/api/v1/cards` | public | search + filter |
| `GET` | `/api/v1/cards/{id}` | public | card with every printing |
| `GET` | `/api/v1/sets` | public | set list |
| `GET` | `/api/v1/sets/{code}` | public | checklist |
| `GET` | `/api/v1/inventory` | user | filtered, sorted, cursor-paged |
| `POST` | `/api/v1/inventory` | user | add or merge |
| `PATCH` | `/api/v1/inventory/{id}` | user | edit |
| `DELETE` | `/api/v1/inventory/{id}` | user | remove |
| `POST` | `/api/v1/inventory/bulk` | user | bulk edit / delete |
| `GET` | `/api/v1/completion` | user | per-set completion |
| `GET` | `/api/v1/sealed` · `POST` · `PATCH` · `DELETE` | user | sealed holdings |
| `GET` | `/api/v1/wishlist` · `POST` · `DELETE` | user | wishlist |
| `GET` | `/api/v1/export` | user | CSV stream, honours filters |
| `POST` | `/api/v1/import` | user | upload → job |
| `POST` | `/api/v1/import/{job}/dry-run` | user | diff, writes nothing |
| `POST` | `/api/v1/import/{job}/commit` | user | atomic apply |
| `GET` | `/api/v1/u/{handle}` | public | whitelist projection |
| `GET` | `/api/v1/admin/catalog/*` | operator | import runs, health |

## Errors

Inherited shape, no exceptions:

```json
{ "error": { "code": "printing_not_found", "message": "Printing not found", "details": {} } }
```

`code` is `snake_case`, stable, and safe to branch on in the client. `message` is human-readable and
may change. `details` carries field-level validation errors keyed by field path.

Codes in use: `printing_not_found` · `inventory_item_not_found` · `set_not_found` ·
`handle_taken` · `quantity_out_of_range` · `currency_required` · `import_row_rejected` ·
`import_bounds_exceeded` · `rate_limited` · `platform_unavailable`.

## Pagination

**Cursor, not offset.** `OFFSET 9000` degrades exactly where the 10,000-row target lives.

```
GET /api/v1/inventory?limit=100&cursor=eyJpZCI6...
→ { "items": [...], "next_cursor": "eyJpZCI6...", "total": 1284 }
```

`next_cursor` is null on the last page. `total` is from the summary table, not a live `COUNT(*)`.

## Filtering

Repeated params are OR within an attribute; distinct params are AND across attributes — the same
semantics the URL-serialised UI filters use, so the two cannot drift.

```
GET /api/v1/inventory?element=fire&element=solar&condition=near_mint
    → (fire OR solar) AND near_mint
```

## Rate limits

60 writes/min/user, 600 reads/min/user. Exceeding returns `429` with `Retry-After` and the standard
error shape with code `rate_limited`.

## Public endpoints

`/cards`, `/sets`, `/u/{handle}` serve unauthenticated. They are cacheable, must never vary on a
user, and `/u/{handle}` is built from a **separate whitelist response model** — never the internal
model with fields filtered out.

## Versioning

`/api/v1` is frozen once the first external user exists. Additive changes only: new optional fields,
new endpoints. A breaking change means `/api/v2` alongside, not a redefinition in place.

## OpenAPI

FastAPI generates it; every endpoint carries a `summary`, a `response_model` and explicit error
responses. The generated schema is the contract the frontend's Zod types are checked against.
