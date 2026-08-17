---
adr: 005
bolt: 005-collection-entry
created: 2026-08-15T17:35:00Z
status: accepted
superseded_by:
---

# ADR-005: Undo adjusts by a delta, and carries the quantity it expects

## Context

Story 018 asks for undo of the last twenty adds, and states the rule precisely: *"undo reverses a
delta, not a row. If a printing was added three times and edited once, undoing the second add must
not delete the holding"*, and *"given an add has since been edited, when I undo it, then it is
refused with an explanation rather than guessing."*

Bolt 004 shipped three inventory writes and none of them can do that:

| Endpoint | Semantics |
|---|---|
| `POST /inventory` | Add. Atomic upsert, merges on `(user_sub, printing_id, merge_condition)`. Bounded `quantity 1–10,000`, `CHECK (quantity > 0)` |
| `PATCH /inventory/{id}` | Edit. **Absolute** values |
| `DELETE /inventory/{id}` | Remove the row |

The forces:

- **Concurrency is not hypothetical here.** The fast-add flow fires requests concurrently by
  design — that is why bolt 004's upsert had to be atomic rather than read-then-write. A user can
  hold `Ctrl+Z`. An undo can race a pending add on the same printing. Any client-side
  read-compute-write over `PATCH` has a window in it, and the window is exactly as wide as the
  round trip the whole bolt is built to hide.
- **The refusal is a requirement, not an error case.** "Refuse when the row changed outside this
  session" has to be able to tell *"changed by my own three adds"* (fine) from *"changed by
  somebody else"* (refuse). A check that cannot distinguish those either corrupts data or blocks
  the normal case.
- **Zero is not a quantity.** Bolt 004: *"a zero-quantity row is a deletion that did not happen."*
  Undoing the add that created a holding has to remove it, not leave a zero.

## Decision

Add **`POST /api/v1/inventory/{id}/adjust`**, taking a signed `delta` and an
`expected_quantity`, and implement it as a single compare-and-swap statement.

```jsonc
// request
{ "delta": -1, "expected_quantity": 3 }

// 200
{ "item_id": "…", "quantity": 2, "deleted": false }

// 409
{ "error": { "code": "inventory_item_changed",
             "message": "That holding changed since you added it",
             "details": { "expected": 3, "actual": 5 } } }
```

```sql
UPDATE inventory_items
   SET quantity = quantity + :delta
 WHERE id = :id AND user_sub = :sub AND quantity = :expected
```

Ownership and concurrency are checked in the same statement, so there is no window between them.
`rowcount = 0` means wrong owner *or* stale expectation, and the two are **not distinguished** in
the response — matching bolt 004's existing rule that cross-user access answers `404` rather than
`403`, because distinguishing "gone" from "not yours" is an enumeration oracle.

A result of zero **deletes the row** and answers `deleted: true`.

The client computes `expected_quantity` from session state as
`baseline_quantity + sum(non-undone deltas this session applied to this holding)`, and uses the
same value for an immediate local refusal — so the common failure is explained without a round
trip, while the server remains the thing that actually holds under concurrency.

## Rationale

The decision is really two: *delta rather than absolute*, and *carry the expectation rather than
check separately*.

Delta, because the requirement is stated as a delta and expressing it as an absolute forces the
caller to compute one — which means reading first, which means racing.

Carrying the expectation, because the alternative is a check-then-act. Reading the quantity,
comparing it to what the session expects, and then PATCHing is three operations with two windows,
and it fails in the precise scenario the story calls out.

### Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|---|---|---|---|
| `POST /inventory` with a negative quantity | No new endpoint | Contradicts the endpoint's meaning; blocked by `quantity 1–10,000` and `CHECK (quantity > 0)` | That endpoint means *add*. Overloading it to mean *subtract* makes both harder to reason about, and the bounds exist for good reasons |
| Client-side read-then-write over `PATCH` | No backend change at all | Loses an undo under concurrent undo, and under undo racing a pending add | Reintroduces one layer up the exact race bolt 004 eliminated. The cheapest option today and the one that produces a bug report nobody can reproduce |
| `quantity_delta` as an optional field on `PATCH` | No new route | One endpoint with absolute *and* relative semantics, switched by which field is present | Reads fine today. In six months somebody sends both, and the answer is whatever the implementation happens to do |
| Separate `GET` then conditional `PATCH` with `If-Match` | Standard HTTP concurrency | Needs an ETag/version column on `inventory_items`, a schema change, and two round trips per undo | More machinery for the same guarantee. The quantity *is* the version for this purpose, and it is already there |
| Server-side undo log | Undo survives a reload | An `add_events` table, a retention policy, and a second source of truth about quantities | Story 018 explicitly scopes undo to the session and says the UI states that. Persisting it is a larger feature nobody asked for |

## Consequences

### Positive

- The undo invariant is enforced **where the races are** — in one SQL statement — rather than in
  a client that cannot see other tabs.
- Ownership and concurrency collapse into one `WHERE` clause, so there is no ordering bug
  available between them.
- The client can refuse instantly and explain, without a round trip, because it computes the same
  `expected_quantity` it would have sent.
- The quantity doubles as the concurrency token, so no schema change and no version column.
- Generalises: any future "adjust by n" (bulk actions in bolt 006, import corrections in bolt 008)
  has an atomic primitive to use rather than inventing another one.

### Negative

- A fourth inventory write endpoint. The surface is now add / edit / adjust / delete, and "which
  do I call" needs a sentence in `api-conventions.md`.
- `expected_quantity` is required, so every caller must track what it expects. That is deliberate
  friction — a caller who cannot say what it expects is a caller that should not be adjusting —
  but it is friction.
- The `409` is a real branch every caller has to handle, not an exceptional one. Two tabs open on
  the same collection will produce it.

### Risks

- **`expected_quantity` becomes a formality.** A future caller that fetches the row purely to fill
  the field has reinstated the read-then-write, with extra steps and a false sense of safety.
  *Mitigation*: this ADR, and a comment on the endpoint saying the field means "what I believe,
  from my own record" and not "what I just read".
- **Condition changes move quantity between rows.** `PATCH` may merge a row into another when its
  condition changes, which changes a quantity this session may have a baseline for. The undo then
  refuses — correct, and the message says so, but it is the least obvious path to the `409` and
  deserves a test.
- **Delta bounds.** An unbounded delta makes the endpoint a way to set any quantity in one call.
  Bounded to ±10,000, matching the existing add bounds.

## Related

- **Stories**: `018-undo-recent-adds` (the requirement), `016-fast-add-flow` and
  `017-set-grid-entry` (the concurrency that makes it necessary)
- **Standards**: `api-conventions.md` gains `inventory_item_changed` → `409`. If a second
  compare-and-swap write appears, the pattern is worth promoting from this ADR into the standard
- **Previous ADRs**: builds directly on bolt 004's atomic-upsert decision, recorded in
  `bolts/004-inventory-core/ddd-02-technical-design.md` rather than as an ADR of its own
