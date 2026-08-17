---
id: 035-scan-add-to-collection
unit: 007-scan-experience
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:32:00Z'
assigned_bolt: 024-scan-experience
implemented: false
---

# Story: 035-scan-add-to-collection

## User Story

**As** a collector
**I want** to note how many of the scanned card I have
**So that** the scan actually accomplishes something — the point was never the identification, it was
getting the card into my collection without typing

## Acceptance Criteria

- [ ] **Given** a confirmed printing, **When** the add is made, **Then** it goes through the
      **existing** inventory write path and inherits merge-on-duplicate
- [ ] **Given** condition, **When** it is set, **Then** it uses a **session carry-forward** default —
      the last condition used, shown persistently and changeable in one tap
- [ ] **Given** quantity, **When** it is set, **Then** it defaults to 1 with a single-tap increment
- [ ] **Given** the same card scanned twice in a session, **When** the second add is made, **Then** the
      holding **increments** rather than creating a second row
- [ ] **Given** any scanned add, **When** the user undoes it, **Then** it uses the existing
      `POST /inventory/{id}/adjust` with a signed `delta` and an `expected_quantity` (ADR-005)
- [ ] **Given** an undo whose holding changed elsewhere, **When** it is attempted, **Then** it
      **refuses with `409` rather than guessing**, per ADR-005
- [ ] **Given** an add, **When** it is made, **Then** it is optimistic with a **visible revert** on
      failure, reusing the mutation layer built for the fast-add flow
- [ ] **Given** `scan-api` being unavailable, **When** an identification was made on-device, **Then**
      the add still completes — the collection backend is a separate service and does not care

## Technical Notes

**Scanning is a new caller, not a new inventory semantic.** Everything about ownership — merge-on-
duplicate, graded copies separate, `quantity > 0`, `user_sub` scoping — already exists and is already
tested. This story adds a caller and nothing else. Any temptation to add a scan-specific write path
should be read as a sign that something is being duplicated.

ADR-005 is load-bearing here and worth reading before implementing: undo adjusts by a **delta** and
carries the quantity it expects, resolving ownership and concurrency in one compare-and-swap `UPDATE`.
That ADR exists because the fast-add flow fires concurrent requests by design — and a batch scan
session (story 037) does exactly the same thing, harder. A client-side read-then-write over `PATCH`
would reintroduce precisely the race the ADR eliminated.

Carry-forward condition matches the phase-1 fast-add behaviour deliberately: the same product should
not have two different ideas about how condition is remembered.

## Dependencies

### Requires
- 034-confirm-printing
- intent 001 / 013-add-inventory-item (implemented)
- intent 001 / 018-undo-recent-adds and ADR-005 (implemented)

### Enables
- 037-batch-scan-session

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| The user owns 3 already | Merge-on-duplicate takes it to 4. The UI shows the resulting total, not just "+1" |
| Undo after the holding changed on the web | `409`, surfaced honestly with what happened. ADR-005 chose refusal over guessing for exactly this |
| The add fails on the server | Optimistic state reverts **visibly**. A silent revert is how a collector ends up believing they added something they did not |
| A graded copy | Separate holding, per the existing invariant. The scan does not detect grading, so this is reached through the printing selection, not inferred |
| Condition carry-forward across app restarts | The session ends at restart; condition returns to the user's default rather than persisting invisibly for weeks |

## Out of Scope

- Any change to inventory rules
- Bulk operations — that is the web app's job
