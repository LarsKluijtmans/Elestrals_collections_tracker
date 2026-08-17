---
unit: 004-collection-experience
bolt: 005-collection-entry
stage: model
status: complete
updated: 2026-08-15T17:00:00Z
---

# Static Model - Collection Entry

Covers `016-fast-add-flow`, `017-set-grid-entry`, `018-undo-recent-adds`.

## Bounded Context

**Entry.** Bolt 004 modelled *what is owned*; this models *the act of recording it*. The
distinction matters because the two have different lifetimes: an `InventoryItem` is permanent and
belongs to a user, whereas everything modelled here dies when the tab closes.

That gives this bolt an unusual shape for a DDD model: **its aggregate lives in the browser.**
There is no `add_sessions` table and there should not be one. A session is a working context — the
condition you have selected, the tally you are watching, the twenty adds you might take back — and
persisting it would turn "close the tab" into a state-management problem for no user-visible gain.
The story says so directly: *"the stack is session-scoped and gone; this is stated in the UI."*

What crosses to the server is only what bolt 004 already accepts: an add, an adjustment, a
removal. This context owns the *sequence* of those calls and the meaning of taking one back.

## Domain Entities

| Entity | Properties | Business Rules |
|---|---|---|
| **AddSession** | `carried`, `records`, `touched`, `started_at` | The aggregate root. Created on entering `/collection/add` or a set grid, destroyed on navigating away. Owns every rule below |
| **AddRecord** | `id`, `printing_id`, `condition`, `delta`, `state`, `applied_at`, `card_label` | One act of adding. **The unit of undo** — not a row, not a card. `delta` may be negative (grid shift-click) and may be >1 (a coalesced burst). `card_label` is captured at add time so the tally and the failure message can name the card without a re-fetch |
| **TouchedHolding** | `printing_id`, `condition`, `baseline_quantity`, `applied_deltas` | Everything this session has done to one holding, and what it looked like before. Exists solely to answer "has somebody else changed this since?" — see the invariant below |

## Value Objects

| Value Object | Properties | Constraints |
|---|---|---|
| **CarriedDefaults** | `condition`, `finish`, `language`, `edition` | Immutable; changing one **replaces** the object. Carries forward across every add until changed, and resets on leaving the session. Defaults are the most common values, not empty — the common case must be `type → Enter` with nothing else touched |
| **QuantityDelta** | signed integer, non-zero | `+1` from a click or an `Enter`, `−1` from a shift-click, `+n` from a coalesced burst. Zero is not a delta and is never recorded |
| **AddState** | `pending` \| `confirmed` \| `failed` \| `undone` | A one-way progression except `confirmed → undone`. A `pending` record already counts in the tally — that is what optimistic means — but cannot be undone until it resolves, because there is nothing on the server yet to reverse |
| **SessionTally** | `total_adds`, `total_quantity`, `recent[5]` | Derived, never stored. `recent` is reverse-chronological and includes `pending` records |
| **UndoStack** | bounded list of `AddRecord` ids, cap 20 | FIFO eviction. The cap is **visible in the UI** rather than silent, so "why can I not undo that one" has an answer on screen |
| **CardLabel** | `name`, `set_code`, `collector_number`, `finish` | Captured at add time. A failure message that says "could not add that one" is not a failure message |

## Aggregates

| Aggregate Root | Members | Invariants |
|---|---|---|
| **AddSession** | `AddRecord`, `TouchedHolding`, `CarriedDefaults`, `UndoStack` | Every rule in the next section. One session per tab; two tabs are two sessions and neither knows about the other, which is correct — they are two people's worth of work as far as the server is concerned |

### The invariant this bolt exists for

> **Undo reverses a delta, not a row — and refuses when it cannot know that it would.**

If a printing was added three times and then edited elsewhere, undoing the second add must not
delete the holding, and must not silently subtract from a number somebody else has since changed.

The naive implementations both fail:

- *Reverse to the quantity recorded after the add* — breaks the moment the same printing is added
  again in the same session, which is the normal case when emptying a box.
- *Always subtract the delta* — silently corrupts a holding that was edited in another tab, and
  the story explicitly requires a refusal rather than a guess.

So `TouchedHolding` keeps what the row looked like **before this session touched it**, plus every
delta the session has applied to it. The session can therefore compute what the quantity *should*
be:

```text
expected = baseline_quantity + sum(delta for each non-undone record on this holding)
```

At undo time, compare `expected` against the server's current quantity:

- **equal** → nobody else has touched it. Reverse the delta.
- **different** → it was edited outside this session. **Refuse, and say so.**

This distinguishes "changed by my own adds" (fine, and expected) from "changed by someone else"
(refuse) using only state the session already has. No version column, no extra round trip, no
guessing.

### Supporting invariants

1. **A pending add already counts.** The tally and the grid badge move on keystroke, not on
   response. The network must never gate the next keystroke — that is the whole product thesis.
2. **A failed add is removed and named.** Rollback is visible and identifies the card. Silence is
   the one unacceptable outcome, because a collector who does not notice a failure has a wrong
   collection and no way to find out.
3. **A delta never drives a holding below zero.** Shift-click at quantity 0 is a no-op, not an
   error flash — the user was clearly aiming at a different tile.
4. **Rapid clicks on one tile coalesce into one delta**, and therefore into **one** `AddRecord`.
   Three clicks in 300ms is one undo entry of `+3`, not three of `+1`. Anything else makes the
   undo stack a keystroke log.
5. **Carried defaults survive an add and a failure.** They reset only on leaving the session. A
   collector who set Foil once should never discover halfway down a box that it stopped applying.
6. **`Enter` acts on the highlighted printing, or on nothing.** With a search in flight it waits
   for the result rather than acting on stale rows. Adding the wrong card silently is worse than
   a pause the user can see.

## Domain Events

| Event | Trigger | Payload |
|---|---|---|
| **AddApplied** | An add is accepted into the session, optimistically | `record_id`, `printing_id`, `condition`, `delta`, `card_label` |
| **AddConfirmed** | The server accepted it | `record_id`, `resulting_quantity` |
| **AddRejected** | The server refused, or the network failed | `record_id`, `card_label`, `reason` |
| **AddUndone** | The user reversed a record | `record_id`, `delta_reversed` |
| **UndoRefused** | The holding changed outside this session | `record_id`, `expected`, `actual` |
| **DefaultsChanged** | Condition, finish, language or edition changed | the new `CarriedDefaults` |

Every one of these is announced to a screen reader via a live region. They are domain events
*because* they are announcements: the accessibility requirement and the state transition are the
same list, which is the cheapest way to guarantee neither drifts from the other.

## Domain Services

| Service | Operations | Dependencies |
|---|---|---|
| **AddSessionService** | `apply(printing, delta, defaults)`, `confirm(record, quantity)`, `reject(record, reason)`, `undo(record)`, `changeDefaults(patch)` | The session aggregate only. Pure state transitions — no I/O, so every rule above is testable without a network |
| **UndoPolicy** | `canUndo(record, actualQuantity) -> allowed \| refused(reason)` | `TouchedHolding`. The invariant above, isolated in one function so it can be tested exhaustively against the cases the story enumerates |
| **DeltaCoalescer** | `push(printing, delta) -> flushes after 300ms idle` | none. Emits one `AddRecord` per burst |

## Repository Interfaces

Client-side gateways over bolt 004's endpoints. Named as repositories because the session treats
them as its persistence boundary, but nothing new is stored.

| Gateway | Entity | Methods |
|---|---|---|
| **InventoryWriteGateway** | InventoryItem | `add(printing_id, condition, quantity, defaults) -> {item_id, quantity}`, `adjust(item_id, delta) -> {quantity}`, `current(item_id) -> {quantity}` |
| **CardSearchGateway** | CardSearchResult | `search(term, signal) -> ranked results` — cancellable, because a slow earlier response must never overwrite a newer one |
| **SetChecklistGateway** | Printing | `checklist(set_code) -> printings with owned quantities` |

`adjust` is the one that needs checking against what bolt 004 actually shipped. Undo needs "change
this row's quantity by −1, atomically" — the same class of operation as the add upsert, not a
read-then-write. If the existing surface only offers an absolute `PATCH`, that is a design-stage
question, and the technical design must resolve it rather than the implementation discovering it.

## Ubiquitous Language

| Term | Definition |
|---|---|
| **Add** | One act of recording ownership. May be +1, −1, or +n from a coalesced burst. The unit of undo |
| **Delta** | The signed quantity an add contributed. Undo reverses *this*, never a row |
| **Carry-forward** | Condition, finish, language and edition persisting from one add to the next. The single largest contributor to the five-second target |
| **Session tally** | Total adds and the last five, live, including pending ones |
| **Touched holding** | A holding this session has changed, with what it looked like before |
| **Baseline quantity** | A holding's quantity before this session's first add to it. The reference point for detecting outside edits |
| **Optimistic add** | An add counted in the UI before the server confirms it |
| **Coalesced delta** | Rapid clicks on one tile, merged into a single add and a single undo entry |
| **Undo refusal** | Declining to reverse an add because the holding changed outside this session — stated, never guessed at |

## Prior decisions loaded

- **ADR-002 (card search — tiered SQL scan, not FULLTEXT)** — its "read when" names the fast-add
  keyboard flow directly. It matters here because it guarantees a *totally ordered* ranking: the
  first result is deterministic, which is the only reason `type → Enter` can be trusted to add the
  card the user meant. A ranking that reshuffled between keystrokes would make the flow unsafe at
  speed.
- **ADR-001 (curated catalog seed)** — relevant only as a caveat: `FE01.csv` is empty, so a real
  timing session needs catalog rows to exist first. That is a prerequisite for the Stage 5
  measurement, not a design constraint.

No prior decision constrains the session model itself; it is new ground.

## Coverage check

| Story | Covered by |
|---|---|
| 016-fast-add-flow | `AddSession`, `CarriedDefaults`, `SessionTally`, supporting invariants 1, 2, 5, 6 |
| 017-set-grid-entry | `QuantityDelta`, `DeltaCoalescer`, supporting invariants 3, 4; shares the session with 016 |
| 018-undo-recent-adds | `AddRecord`, `TouchedHolding`, `UndoStack`, `UndoPolicy`, and the invariant this bolt exists for |
