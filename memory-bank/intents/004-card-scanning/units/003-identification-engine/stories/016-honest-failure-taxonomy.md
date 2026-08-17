---
id: 016-honest-failure-taxonomy
unit: 003-identification-engine
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T13:55:00Z'
assigned_bolt: 020-identification-ladder
implemented: false
---

# Story: 016-honest-failure-taxonomy

## User Story

**As** a collector whose card was not recognised
**I want** to be told that plainly, and given a way forward
**So that** I do not add the wrong card because the app offered me its least-bad guess and I was going
quickly

## Acceptance Criteria

- [ ] **Given** no candidate above the reject floor, **When** the result renders, **Then** it says "no
      confident match" and does **not** render a ranked list of noise
- [ ] **Given** a failure, **When** it is reported, **Then** it carries exactly one of
      `no_text_read`, `no_catalog_match`, `uncovered_printing`, `below_floor`, `timed_out`
- [ ] **Given** each reason, **When** failures are aggregated, **Then** they are counted separately, so
      the dominant failure mode is visible without reading rows
- [ ] **Given** a failure, **When** the user is offered a way forward, **Then** search-by-name and
      manual entry are offered, **pre-filled** with whatever text the OCR did read
- [ ] **Given** a failure, **When** it completes, **Then** the capture is still stored with its reason —
      unmatched captures are the queue of what the corpus and the catalog are missing
- [ ] **Given** a `no_catalog_match` caused by a stale index, **When** it is reported, **Then** the
      index version travels with it so the cause is distinguishable

## Technical Notes

The five reasons are not error codes for developers; they are five different product problems with
five different owners:

| Reason | What it actually means | Who fixes it |
|---|---|---|
| `no_text_read` | The camera or the card defeated OCR | The capture UX — lighting hints, framing guides |
| `no_catalog_match` | Text was read; the catalog has no such card | The catalog — this set is not compiled yet |
| `uncovered_printing` | The catalog has it; the corpus has no fingerprint | Curation — photograph it |
| `below_floor` | Everything was tried and nothing was close enough | The engine |
| `timed_out` | The budget expired | Performance |

Aggregating them separately is what turns a vague "the scanner is bad" into "84% of failures are
`uncovered_printing`, so the problem is coverage, not the matcher." That distinction is the difference
between a week of model work and an afternoon of photography.

**Pre-filling the fallback is the difference between a dead end and a detour.** A user who has just
watched the app read "Vipyro" and fail should not then type "Vipyro".

## Dependencies

### Requires
- 013-identification-ladder

### Enables
- 021-curation-queue — `uncovered_printing` failures order the queue
- 026-rejection-analytics
- 034-confirm-printing — which renders this state

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Several reasons apply at once | The **most actionable** wins, in the order above; the others are recorded in the prediction row rather than discarded |
| A card genuinely is not in the catalog | `no_catalog_match` with the pre-filled name is the best possible outcome — it becomes a catalog gap someone can close |
| The user retries the same card and fails again | Both captures stored. A repeated failure on one card is a stronger signal than two failures on different cards |
| Failure rate spikes after a release | Visible immediately in the per-reason counts, which is why they are counted rather than logged |

## Out of Scope

- The search flow itself — it exists (intent 001, story 010); this story hands off to it
- The curation queue that consumes these signals (unit 005)
