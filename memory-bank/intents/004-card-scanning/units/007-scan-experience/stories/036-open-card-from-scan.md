---
id: 036-open-card-from-scan
unit: 007-scan-experience
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:33:00Z'
assigned_bolt: 024-scan-experience
implemented: false
---

# Story: 036-open-card-from-scan

## User Story

**As** a collector who scanned a card to find out what it is
**I want** to jump straight to that card's page
**So that** identifying a card and owning a card are two different things I can do — sometimes I am
holding someone else's card and just want to know what it is worth

## Acceptance Criteria

- [ ] **Given** a scan result, **When** actions are offered, **Then** "open card" is **distinct from**
      "add to collection" and neither implies the other
- [ ] **Given** the mobile app, **When** "open card" is chosen, **Then** it opens the read-only card
      detail of story 030
- [ ] **Given** the web app, **When** "open card" is chosen, **Then** it navigates to the existing
      `/cards/:id`
- [ ] **Given** an in-progress batch session, **When** the user opens a card and returns, **Then** the
      session is **intact** — tally, carry-forward condition and queued adds all preserved
- [ ] **Given** a candidate the user has not confirmed, **When** "open card" is chosen, **Then** it
      opens the card that candidate names, without recording a confirmation

## Technical Notes

The separation in the first criterion is the whole story. A flow where identifying a card
automatically adds it — or where the only way to see the card is to add it first — is a flow that
fills collections with cards people do not own. Someone at a trade table checking what a friend's card
is worth must be able to do that without polluting their inventory.

The session-preservation criterion is where this story is most likely to break in practice. Navigation
that unmounts the scan session is the default behaviour of most routing setups, and losing a
twenty-card tally to a curiosity tap is the kind of bug that stops people using the batch flow at all.
The shared state machine holds the session outside the navigation tree for this reason.

The last criterion is subtle and worth keeping: opening a card to *check* whether it is the right one
is a legitimate way to resolve an ambiguous candidate list. It must not count as confirming that
candidate, because the user may come back and pick a different one — and recording the wrong label
would poison the flywheel with exactly the confident-looking error it is meant to catch.

## Dependencies

### Requires
- 034-confirm-printing
- 030-mobile-card-detail-and-completion — for the mobile target
- intent 001 / 012-card-detail (implemented) — for the web target

### Enables
- Nothing — this is a leaf

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| The user opens a card, adds from the card page instead | Fine. That is an ordinary inventory add through an existing surface; the capture records that the scan was not the route |
| Deep-linking into the app from a scan result on web | Out of scope; the two surfaces navigate within themselves |
| The card has no approved image | Renders as it does everywhere else — honest empty state |
| The user opens a card while offline | Mobile shows the cached detail where available (story 031); web shows an offline state |

## Out of Scope

- Cross-surface deep links
- Any write from this path
