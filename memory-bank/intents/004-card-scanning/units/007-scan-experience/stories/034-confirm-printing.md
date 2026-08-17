---
id: 034-confirm-printing
unit: 007-scan-experience
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:31:00Z'
assigned_bolt: 024-scan-experience
implemented: false
---

# Story: 034-confirm-printing

## User Story

**As** a collector holding a foil card
**I want** the app to tell me which card it is and let me confirm the finish
**So that** the copy recorded is the copy I own — because the camera can read the name and the number,
and it cannot see whether the card is shiny

## Acceptance Criteria

- [ ] **Given** an identification, **When** candidates render, **Then** they are ranked, capped at 5,
      each with its **calibrated** confidence and the printing attributes it asserts
- [ ] **Given** a card with exactly one printing, **When** it is confirmed, **Then** **no printing
      question is asked**
- [ ] **Given** a card with several printings, **When** they are offered, **Then** the most common is
      pre-selected and **finish is visibly the field in question**
- [ ] **Given** a pre-selection, **When** the user does nothing, **Then** **nothing is committed** — the
      add action is always the user's
- [ ] **Given** a confirmation, **When** it is recorded, **Then** it is stored as a label against the
      capture, **including when the user changes the pre-selection**
- [ ] **Given** a correction, **When** it is stored, **Then** it is flagged as a correction, because it
      is the most valuable label the system can receive
- [ ] **Given** two candidates within the ambiguity margin, **When** they render, **Then** they are
      presented as a **choice**, not as an answer with an alternative beneath it
- [ ] **Given** no confident match, **When** the result renders, **Then** story 016's honest failure is
      shown with its pre-filled search fallback
- [ ] **Given** the image, **When** a candidate has an approved display image, **Then** it is shown
      beside the name — recognising a card by eye is faster than reading its attributes

## Technical Notes

This story is where the decision taken at Checkpoint 1 becomes visible: **finish is confirmed, not
detected.** A two-frame tilt heuristic could detect foil from a moving specular highlight, and a model
trained on flywheel labels could learn it. Both belong to a future recogniser-V2 intent. What this
story owes that intent is its training data, and it produces it on every single scan — a confirmation
is a finish label, and a correction is a finish label about a case the system got wrong.

Storing the correction, not merely the final state, is the criterion most easily lost in
implementation. The natural code writes the chosen printing and moves on; what is needed is *offered*
versus *chosen*, so that "the engine ranked the reverse-foil third and the user picked it" is
recoverable.

Pre-selection uses the most common printing for that card — usually the base rarity in the base finish.
It is a suggestion that saves a tap in the common case and never a commitment.

## Dependencies

### Requires
- 013-identification-ladder
- 015-calibrated-confidence
- 016-honest-failure-taxonomy
- 033-capture-and-crop

### Enables
- 035-scan-add-to-collection
- 021-curation-queue — corrections are its highest-value queue items

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| The correct card is not among the 5 candidates | The failure path is offered alongside the candidates — "none of these" leads to search, and that capture becomes a high-value curation item |
| A card has 8 printings | All are reachable; the list is grouped by finish so the question stays "which finish" rather than "which of eight rows" |
| The user picks a candidate ranked 4th | Recorded as a correction with the full offered ranking. This is exactly the signal unit 003 needs |
| Confidence is unavailable because no harness run exists | Qualitative band, no percentage (story 015). The flow is unchanged |
| The user scans the card back | `no_confident_match` with a "turn the card over" hint from story 014 |

## Out of Scope

- Writing to inventory (story 035)
- Detecting finish automatically — a future intent, by decision
