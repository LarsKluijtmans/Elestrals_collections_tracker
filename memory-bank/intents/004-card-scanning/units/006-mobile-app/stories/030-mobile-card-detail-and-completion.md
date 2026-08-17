---
id: 030-mobile-card-detail-and-completion
unit: 006-mobile-app
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:23:00Z'
assigned_bolt: 023-mobile-app-shell
implemented: false
---

# Story: 030-mobile-card-detail-and-completion

## User Story

**As** a collector who has just scanned a card
**I want** to see the card itself and how close that set is to complete
**So that** "which one is it" is followed by the two things I actually want to know — what is it worth,
and do I need it

## Acceptance Criteria

- [ ] **Given** a card, **When** its detail renders, **Then** it shows the card's attributes, its
      printings, the approved image where one exists, and how many of each printing the user holds
- [ ] **Given** the detail view, **When** it is used, **Then** it is **read-only** — no add, no edit, no
      wishlist toggle
- [ ] **Given** price data, **When** intent 002 has published a rollup for a printing, **Then** it is
      displayed **with its confidence**, using the same component and the same rules as the web app
- [ ] **Given** no price data, **When** the detail renders, **Then** it shows the honest empty state
      rather than a zero
- [ ] **Given** set completion, **When** it is shown, **Then** it is **read from the existing endpoint**
      and not recomputed on the device
- [ ] **Given** a set, **When** completion is displayed, **Then** it uses the printed set size as the
      denominator, consistent with the web app

## Technical Notes

Recomputing completion on the device would be a second implementation of a rule that already exists
server-side, and the two would drift. The completion projection is written on inventory write
(intent 001, story 023) precisely so that clients read rather than calculate.

The price display inherits intent 002's hardest-won rule: **no figure renders without its
confidence.** The `ConfidencePill` is a required prop on the money component there, and it must be
required here too. A mobile app is exactly where a "simplified" money display without its confidence
would be argued for, and the answer is no — the whole intent 002 design rests on that pairing.

This story is also where scanning starts to pay off beyond data entry: the scan says which card, the
card page says what it is worth, and completion says whether you need it. Those three answers are the
reason to have a phone in your hand at a trade table.

## Dependencies

### Requires
- 029-mobile-collection-browse
- intent 001 / 012-card-detail and 023-set-completion (both implemented)
- intent 002 / 019-card-price-history — optional; absent means the price section is simply not there

### Enables
- 036-open-card-from-scan

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| `harvest-api` is down | Price section shows last-known rollups, exactly as the web app does — the projection is a table, not a live call |
| A printing has no approved image | Honest empty state; the rest of the detail renders normally |
| A set's completion is 0 | Displayed as 0, not hidden. A set you own nothing from is a legitimate view |
| Price data exists at `low` confidence | Shown, labelled `low`. Suppressing low-confidence figures would misrepresent the market as sparser than it is |

## Out of Scope

- Price charts. A history chart on a phone is a real design problem and not one this intent needs to
  solve — the current figure with its confidence is enough
- Any write action
