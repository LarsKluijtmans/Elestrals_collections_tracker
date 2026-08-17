---
unit: 004-collection-experience
bolt: 005-collection-entry
stage: design
status: complete
updated: 2026-08-15T17:20:00Z
---

# Technical Design - Collection Entry

## Architecture Pattern

**Client-side aggregate over a thin write API.**

The domain model put the aggregate in the browser, so the architecture follows: an
`AddSessionProvider` holds the session, a reducer applies every state transition, and TanStack
Query owns the network. React context for client state and TanStack Query for server state is the
project's standing choice (`tech-stack.md`) and it fits exactly — the session *is* client state,
and the holdings it touches *are* server state.

The one thing that must not happen is the two being conflated. The tally is not a query result and
must never be re-derived from a refetch; it is the session's own record of what it did, including
adds the server has not answered yet.

```text
┌──────────────────────────────────────────────────────────┐
│ Presentation   AddPage · SetGridPage · SearchBox ·        │
│                SessionTally · UndoList                    │
├──────────────────────────────────────────────────────────┤
│ Application    useAddSession()  — one hook, all intents   │
│                (add, adjust, undo, changeDefaults)        │
├──────────────────────────────────────────────────────────┤
│ Domain         addSessionReducer · undoPolicy ·           │
│                deltaCoalescer      (pure, no I/O)         │
├──────────────────────────────────────────────────────────┤
│ Infrastructure inventoryApi · searchApi (TanStack Query)  │
└──────────────────────────────────────────────────────────┘
```

The domain layer being pure is the load-bearing part: every invariant from stage 1 is a reducer
transition or a policy function, testable without a DOM and without a network. If a rule needs a
component rendered to test it, it has been put in the wrong layer.

## The API gap, and how it is closed

Stage 1 flagged this: undo needs *"change this row's quantity by −1, atomically"*, and bolt 004
did not ship it. Its surface is `POST /inventory` (add, atomic upsert), `PATCH /inventory/{id}`
(edit, absolute), `DELETE /inventory/{id}`.

Read-then-write from the client is not an option here, and not for a theoretical reason: the fast
add flow **fires concurrent requests by design**, a user can hold `Ctrl+Z`, and an undo can race a
pending add on the same row. Computing `current − 1` in the browser and PATCHing it is precisely
the pattern bolt 004 went out of its way to avoid, reintroduced one layer up.

Four options were considered:

1. `POST /inventory` with a negative quantity — refused by bolt 004's own bounds
   (`quantity 1–10,000`, `CHECK (quantity > 0)`), and rightly: that endpoint means *add*.
2. Client-side read-then-write over `PATCH` — loses an undo under concurrency. Rejected.
3. **A new endpoint, `POST /inventory/{id}/adjust`.** Atomic, owner-scoped, delta-based.
4. An optional `quantity_delta` on `PATCH` — mixes absolute and relative semantics in one
   endpoint. Reads fine today, confuses everyone in six months.

**Option 3.** It is a small, well-scoped addition, and it is where the concurrency actually lives.

### `POST /api/v1/inventory/{id}/adjust`

```jsonc
// request
{ "delta": -1, "expected_quantity": 3 }

// 200
{ "item_id": "…", "quantity": 2, "deleted": false }

// 409 — somebody else changed this row
{ "error": { "code": "inventory_item_changed",
             "message": "That holding changed since you added it",
             "details": { "expected": 3, "actual": 5 } } }
```

Two decisions inside it:

**`expected_quantity` makes it a compare-and-swap.** Stage 1's undo rule — reverse if the holding
is what this session expects, refuse if somebody else changed it — is enforced *server-side, in
the same statement as the write*. Computing `expected` client-side and comparing before a PATCH
would be a check-then-act with a window in it, which is the same bug in a different place.

**Reaching zero deletes the row.** Bolt 004 is explicit that *"a zero-quantity row is a deletion
that did not happen"*, and its `CHECK (quantity > 0)` would reject one anyway. Undoing the add that
created a holding removes it and returns `deleted: true`, so the client can drop the row rather
than render a zero.

Implemented as one statement plus the same in-transaction completion recompute every other
inventory write does:

```sql
UPDATE inventory_items
   SET quantity = quantity + :delta
 WHERE id = :id AND user_sub = :sub AND quantity = :expected
```

`rowcount = 0` means either wrong owner or changed quantity. Both answer **404 / 409 without
distinguishing** — telling a stranger that an id exists but is not theirs is the enumeration
oracle bolt 004's security design already refuses.

## API Design

| Endpoint | Method | Auth | Used by | Notes |
|---|---|---|---|---|
| `/api/v1/cards/search` | `GET` | public | 016 | Existing (bolt 003). Cancelled on each keystroke |
| `/api/v1/inventory` | `POST` | user | 016, 017 | Existing (bolt 004). Atomic upsert |
| `/api/v1/inventory/{id}/adjust` | `POST` | user | 017, 018 | **New.** Delta + compare-and-swap |
| `/api/v1/sets/{code}` | `GET` | public | 017 | Existing (bolt 003). Set checklist |
| `/api/v1/completion` | `GET` | user | 017 | Existing (bolt 004). Owned badges on the grid |

New error code: `inventory_item_changed` → `409`. Added to `api-conventions.md`.

## Layer Structure — frontend

```text
frontend/src/
  session/
    AddSessionContext.tsx     provider + useAddSession()
    addSessionReducer.ts      every stage-1 transition, pure
    undoPolicy.ts             allowed | refused(reason)
    deltaCoalescer.ts         300ms burst → one AddRecord
    types.ts                  AddRecord, TouchedHolding, CarriedDefaults
  pages/collection/
    AddCards.tsx              /collection/add
    AddFromSet.tsx            /collection/add/set/:setCode
  components/add/
    AddSearchBox.tsx          the keyboard contract
    CarriedDefaultsBar.tsx    condition/finish, Alt+C / Alt+F
    SessionTally.tsx          total + last five + undo
    SetGrid.tsx               virtualised tiles
    LiveAnnouncer.tsx         one aria-live region for the whole session
```

`session/` is not under `pages/` deliberately: both entry surfaces share one session, and a
provider living inside either page would die on navigation between them.

## Key mechanics

### The keyboard contract (016)

| Key | Behaviour |
|---|---|
| *(page load)* | Focus is already in the search field. `autoFocus`, and no click needed to start |
| type | Debounced 120ms; the previous request is `AbortController`-cancelled so a slow earlier response can never overwrite a newer set |
| `↓` / `↑` | Move the highlight. `aria-activedescendant` on the input; the listbox never takes focus |
| `Enter` | Add the highlighted printing. **If a search is in flight, await it first** — acting on stale rows would add the wrong card, and a visible pause is the lesser failure |
| `Esc` | Clear the field, keep focus |
| `Ctrl/Cmd+Z` | Undo the last add — **only when the field is empty**, so it does not fight native text undo |
| `Alt+C` / `Alt+F` | Condition / finish, without leaving the keyboard |

`autocomplete="off"` on the search field. An autofilled street address in a card search is pure
noise, and browsers will offer one.

### Optimistic add

TanStack Query `onMutate` → `onError` rollback, per story 016. Concretely:

1. Reducer applies `AddApplied`. The tally moves *now*; the keystroke path is never gated on a
   round trip.
2. `POST /inventory` fires. Adds are **concurrent, not queued** — which is exactly why bolt 004's
   upsert had to be atomic rather than read-then-write.
3. `onSuccess` → `AddConfirmed`, carrying the server's resulting quantity into the
   `TouchedHolding`.
4. `onError` → `AddRejected`. The row is removed from the tally, and an inline non-blocking
   message **names the card**. `card_label` was captured at add time for exactly this, so the
   message does not need a fetch that may also fail.

### The grid (017)

Tiles are virtualised (TanStack Virtual — already the project's choice for the 10k-row collection
table) and **reserve their aspect ratio before art loads**. Story 017 puts it plainly: a grid that
jumps while you are clicking it is a grid that records the wrong card.

Click is `+1`, shift-click is `−1`. Shift-click at 0 is a no-op with no error flash — the user was
aiming at a different tile. Rapid clicks on one tile pass through `deltaCoalescer`, flushing after
300ms idle into **one** request and **one** undo entry.

A `+n` burst goes to `POST /inventory` with `quantity: n`. A net-negative burst goes to
`/adjust`. A burst that nets to zero sends nothing.

### Undo (018)

`undoPolicy(record, touched)` returns `allowed | refused(reason)` from session state alone, then
`/adjust` re-checks it atomically. Two layers, and neither is redundant: the client one gives an
instant, explained refusal without a round trip; the server one is what actually holds under
concurrency.

The stack is capped at 20 with FIFO eviction, and **the cap is visible** — "20 most recent" sits
above the list, so "why can I not undo that one" has an answer on screen rather than in a comment.

A `pending` record cannot be undone: there is nothing on the server yet to reverse. The undo
control for it is disabled rather than hidden, so it does not shift the list under the cursor.

## Security Design

| Concern | Approach |
|---|---|
| Identity | The validated JWT `sub`. `/adjust` takes an item id and derives the owner from the token, never from the request |
| Cross-user access | `404`, never `403` — one explicit test, matching every other inventory endpoint |
| Ownership + concurrency in one statement | The `WHERE id AND user_sub AND quantity = :expected` clause is both checks at once; there is no window between them |
| Bounds | `delta` is a non-zero integer within ±10,000; the resulting quantity is bounded by the existing `CHECK` |
| Session state | Lives in memory only. Nothing about an add session is persisted, so nothing about it can leak |

## NFR Implementation

| Requirement | Approach |
|---|---|
| **Median add < 5s** | Carry-forward, a preselected most-common printing, and focus already in the field. The target is decisions removed, not milliseconds saved — the bolt notes are explicit that if we miss it, the fix is the interaction and not the API |
| **100 cards < 10min** | Optimistic adds, concurrent requests, no modal, no confirmation step |
| Search < 150ms p95 | Existing (ADR-002's tiered scan). Debounce 120ms + cancellation keeps the perceived latency at one request's worth |
| Grid at 300 printings, 60fps | Virtualisation + reserved aspect ratios; badges update from session state, not a refetch |
| Adjust p95 < 200ms | One `UPDATE` + the scoped completion recompute, same shape as every other inventory write |

## Accessibility

`ux-guide.md` §232-237 binds three things, and all three are in the design rather than bolted on:

- **Visible focus** on every interactive element — 2px `--brand-ring`, offset 2. Never
  `outline: none`, and the search field keeps focus through the entire flow.
- **The add flow is keyboard-only end to end**, because that is how anyone entering 200 cards will
  actually use it.
- **Live regions announce optimistic saves and their failures.** One `aria-live="polite"` region
  for the session, fed by the stage-1 domain events. Failures are `assertive`.

The domain events *are* the announcements. Keeping them one list is the cheapest way to guarantee
a new state transition cannot ship silent.

## Data Model

No new tables. `inventory_items` and `set_completion` are unchanged; `/adjust` is a new operation
over the existing schema.

## Testing Approach

| Layer | What |
|---|---|
| Reducer / policy | Every stage-1 invariant, pure. Especially: undo after re-adding the same printing (allowed), undo after an outside edit (refused), a coalesced burst is one entry, a pending add cannot be undone |
| Backend | `/adjust`: happy path, wrong owner → 404, stale `expected_quantity` → 409, reaching zero deletes, concurrent adjust does not lose one |
| Component | The keyboard contract, pinned: focus on load, `↓`+`Enter` adds and refocuses, `Enter` mid-flight waits, `Ctrl+Z` only when empty |
| Manual | **The timed session.** Median add and 100-card total, with a first-time user. This cannot be automated and is the criterion the bolt actually exists to hit |

## Stage 3 (ADR analysis) — recommendation

**One candidate.** The `/adjust` compare-and-swap endpoint is a new integration pattern: it is the
first delta-based write in the API, and the first use of an `expected_*` field as an optimistic
concurrency token. Everything else in the codebase writes absolutes or atomic upserts. That is the
kind of decision the next person adding a write endpoint will want the reasoning for, and it is
exactly the "integration pattern / API contract" trigger in the bolt-type's ADR guidance.

Recommend creating it. The alternative — leaving the rationale in this document — buries it where
somebody designing a *different* endpoint will not look.
