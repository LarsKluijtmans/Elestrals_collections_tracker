---
id: 037-batch-scan-session
unit: 007-scan-experience
intent: 004-card-scanning
status: ready
priority: should
created: '2026-08-17T14:34:00Z'
assigned_bolt: 024-scan-experience
implemented: false
---

# Story: 037-batch-scan-session

## User Story

**As** a collector with a shoebox of 400 cards
**I want** to scan card after card without returning to a menu
**So that** the feature is actually faster than typing — which it is not, if every card costs three
taps of navigation on top of the scan

## Acceptance Criteria

- [ ] **Given** an add, **When** it completes, **Then** the camera **stays live** for the next card
- [ ] **Given** an open session, **When** it renders, **Then** a running count and the carry-forward
      condition are visible at all times
- [ ] **Given** a session, **When** the user reviews it, **Then** each add is **individually undoable**
      from the session list without leaving the camera
- [ ] **Given** a backgrounded app, **When** it returns, **Then** the session survives and resumes
- [ ] **Given** no network, **When** adds are made, **Then** they **queue locally** and the session
      continues
- [ ] **Given** the network returning, **When** the queue reconciles, **Then** applied adds are
      confirmed and a **conflicting queued add surfaces** rather than being dropped
- [ ] **Given** a session ending, **When** it summarises, **Then** it reports what was added and what
      failed
- [ ] **Given** a batch session, **When** median time per card is measured, **Then** it is ≤ 6s from
      camera-open to quantity recorded

## Technical Notes

This is the story the whole intent is judged on. Everything upstream can be correct and the product
still fails if entering a box takes as long as typing it.

**Queued adds and ADR-005 interact directly.** A queue flushing after reconnect fires concurrent
delta-adjusts, which is precisely the race that ADR-005's compare-and-swap exists for. A queued add
whose `expected_quantity` no longer holds must surface — the user changed something on the web, or an
earlier queued item already applied — and surfacing it is the difference between a reliable tool and
one that quietly loses a card from a box of 400. Silent dropping is the single failure mode a collector
cannot detect, because they have no independent record of what they scanned.

Session persistence must survive a process kill, not just a background. Phones kill backgrounded apps
with live cameras aggressively, and losing a session that way would be indistinguishable from the app
being broken.

Prioritised **Should** rather than Must because single-card scanning is a complete, useful feature
without it. That said, the 6s business goal cannot be met without this story, so "should" here means
"the intent ships without it only if something has gone wrong", not "optional".

## Dependencies

### Requires
- 035-scan-add-to-collection
- 031-offline-collection-cache — shares the persistence approach
- intent 001 / ADR-005 delta-adjust (implemented)

### Enables
- Nothing — this is the payoff of the payoff

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| 400 cards in one session | Session list is virtualised; the queue is bounded and flushes progressively rather than at the end |
| The app is killed mid-session | Session and queue restored from persistent storage on next launch, with an explicit "you have 23 unsent adds" state |
| A queued add's printing was deleted from the catalog | Surfaces as a conflict with the card named. It cannot be silently dropped |
| The user undoes an add that is still queued | Removed from the queue without ever reaching the server, which is cheaper and equally correct |
| Battery dies mid-session | Same as process kill — the queue is on disk |
| Two devices scanning into one account | Both queues reconcile; merge-on-duplicate makes the result correct regardless of order |

## Out of Scope

- Scanning multiple cards in one frame
- Continuous auto-capture without confirmation — every add is still the user's action (story 034)
