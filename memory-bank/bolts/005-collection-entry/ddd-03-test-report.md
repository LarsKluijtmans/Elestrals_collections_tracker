---
bolt: 005-collection-entry
stage: test
status: partial
created: 2026-08-17T18:45:00Z
---

# Test Report: 005-collection-entry

**Status: `partial`, and the reason is a single criterion.** Every automated assertion the bolt asks
for is written and passing. The one thing that decides whether this bolt succeeded — *median add
under five seconds, 100 cards under ten minutes, measured with a first-time user* — has not been
run, because it needs a person in a room with a box of cards. See
[Not verified](#not-verified--and-why-it-blocks-completion).

## Automated

```
backend/.venv  → pytest -q                       202 passed
frontend       → vitest run                      130 passed  (9 files)
frontend       → vitest run --coverage           95.4% statements on the bolt's own surface
frontend       → tsc --noEmit                    clean
```

Backend went 178 → 202 (+24), frontend 17 → 130 (+113).

### New suites

| Suite | Tests | Covers |
|---|---|---|
| `backend/tests/test_inventory_adjust.py` | 17 | the compare-and-swap: delta reversal, zero-deletes-the-row, stale expectation → `409` with both numbers, cross-user → `404` not `409`, guard rails, completion recompute, one-statement proof, **two racing undos** |
| `backend/tests/test_inventory_api.py` (added to) | 7 | `/adjust` over HTTP: shapes, `409` details, `400` vs `422`, and the cross-user test the bolt requires **per endpoint** |
| `frontend/src/session/addSessionReducer.test.ts` | 22 | every state transition: baseline-on-first-touch, the undo cap's FIFO eviction, tally under failure and undo, carried defaults surviving both |
| `frontend/src/session/undoPolicy.test.ts` | 14 | `expectedQuantity` and every refusal path — including **undoing one of three adds expects three** |
| `frontend/src/session/deltaCoalescer.test.ts` | 10 | one add per burst, per printing, net-zero sends nothing, `flushAll` on unmount |
| `frontend/src/session/AddSessionContext.test.tsx` | 24 | the session against a mocked transport: optimism, visible revert, the delta and expectation `/adjust` receives, the `409` refusal, grid badges |
| `frontend/src/components/add/AddSearchBox.test.tsx` | 20 | **the keyboard contract**, step by step |
| `frontend/src/components/add/SetGrid.test.tsx` | 11 | click +1, shift-click −1, burst coalescing, badges, accessible names |
| `frontend/src/components/add/CarriedDefaultsBar.test.tsx` | 12 | carry-forward, `Alt+C` / `Alt+F`, wrap-around, listener teardown |

### Coverage

Frontend coverage is scoped to `src/session/**` and `src/components/add/**` — the code that carries
rules. A number averaged over page shells and generated locale files would not answer the question
the threshold is asking. Thresholds are enforced in `vite.config.ts`, so this cannot quietly rot.

| | Statements | Branches | Functions | Lines |
|---|---|---|---|---|
| frontend (bolt surface) | 95.4% | 88.7% | 95.4% | 96.7% |
| backend (whole app) | 87% | — | — | — |
| backend (inventory write surface) | 94% | — | — | — |

## Two bugs the test stage caught

### 1. The live region was silent on the second of two identical adds

Stage 3 put a timestamp in the announcement value with this comment: *"`at` is part of the value so
two identical messages in a row still re-announce."* The first new reducer test failed on it —
`Date.now()` has millisecond resolution and both adds landed inside the same millisecond, so the
two announcements were indistinguishable.

The fix for that is a monotonic `seq` rather than a clock: a guarantee instead of a probability that
gets *worse the faster the flow gets*, in the flow whose entire purpose is speed.

But writing the test exposed the larger half, which no amount of state identity would have fixed. A
screen reader announces a live region when **its content changes**. Two identical adds mutate one
region from `"Added Atlas ×1"` to `"Added Atlas ×1"` — no change, no announcement, silence. The
timestamp made React re-render; it never made the DOM differ, because it was never rendered.

`LiveAnnouncer` now double-buffers each politeness level: consecutive announcements alternate slots
on the parity of `seq`, so every announcement lands in a region that was empty and empties the one
that held the last. Two mutations, one of them empty→text, which is what gets read out.

This is not an edge case. It is a collector emptying a box of duplicates, which is the flow's main
use, and the bolt lists *"screen reader announces success and failure via a live region"* as a
success criterion. It would have shipped broken and been discovered by a screen-reader user.

### 2. `compare_and_adjust` left a stale quantity in the identity map

Caught by `test_the_quantity_is_read_back_after_the_write`. The atomic `UPDATE` bypasses the ORM, so
the session's identity map still held the pre-update row and a caller reading the item back through
the same session saw the old number. The same trap `upsert_merge` documents from bolt 004, hit again
one method over — now fixed with `expire_all()` and pinned by a test, so the third time it is a
regression rather than a discovery.

## What the concurrency test actually proves

`test_concurrent_undos_only_one_wins` runs two real threads on two real SQLite connections against
one row, both carrying `expected_quantity=2`. Exactly one applies; the other must be **refused, not
crash** — a `database is locked` there would mean the statements are serialising by luck rather than
by the `WHERE` clause.

Every other assertion in that file also passes against a read-compare-write implementation. That is
the whole point: ADR-005 rejected read-then-write because it reintroduces one layer up the exact
race bolt 004's atomic upsert eliminated, and only a real race distinguishes the two.

MySQL's own row locking under that race is now covered by `scripts/verify_mysql.py` steps **[8]** and
**[9]**, added in this stage — but that script needs the platform stack, so those two steps are
**written and unrun** here, exactly as the grant tests in `harvest/` are.

## Success criteria

| Criterion | State |
|---|---|
| Focus is in the search field on load; no click needed | met — `puts focus in the field on load` |
| `type 3 chars → ↓ → Enter` adds, clears and refocuses | met — `adds the highlighted card, clears the field and refocuses` |
| Condition and finish carry forward between adds | met — reducer test plus `CarriedDefaultsBar` suite |
| Session tally with the last five adds; undo works per-add | met — `shows the five most recent, newest first` |
| Grid mode: click +1, shift-click −1, no reload, badges update instantly | met — `SetGrid` suite plus the badge tests |
| Optimistic add reverts **visibly** on failure, naming the card | met — `reverts the tally and names the card on screen` |
| Screen reader announces success and failure via a live region | met **after the fix above** |
| **Measured**: median add < 5s, 100 cards < 10min, first-time user | **not run** |
| Coverage > 80%, including a component test pinning the keyboard contract | met — 95.4%, and `AddSearchBox.test.tsx` is that test |

## Not verified — and why it blocks completion

**The timed session with a real person.** The bolt's objective is a number, its notes say what to do
if the number is missed, and the number cannot be measured by a test suite. What the automated tests
prove is that the *interaction* is correct — the keys do what they claim, nothing is lost, nothing is
silent. Whether a first-time collector clears 100 cards in ten minutes is a different question, and
the tests cannot answer it.

The bolt notes are worth re-reading before that session, because they pre-commit the response: if the
median is missed, fix the interaction — fewer required fields, better defaults, more aggressive
carry-forward — and do **not** optimise an API already answering in 200ms. The bottleneck will be
decisions the user has to make.

**Also unrun, both needing the platform stack:**

- `scripts/verify_mysql.py` steps [8] and [9] — the compare-and-swap under MySQL's row locking, and
  adjust-to-zero deleting rather than storing a zero.
- The p95 write budget from bolt 004 (< 200ms including recompute) against `/adjust` specifically.
  `scripts/bench.py` measures the add path, not this one.

## Notes

The reducer, `undoPolicy` and `deltaCoalescer` are tested with no DOM at all, and that is the shape
worth keeping: **46 of the 130 frontend tests need nothing rendered**. The rules that decide whether
a collector's data is right are the ones that must never be hard to test, and the split stage 3 chose
— reducer owns the rules, context owns the I/O — is what made this stage cheap rather than a
rendering exercise.

One thing the coverage number hides: `AddSessionContext.tsx` sits at 88.7% branches and the gap is
concentrated in error paths that need two failures at once (a rejected baseline read *and* a rejected
add). Worth knowing rather than worth chasing.
