---
unit: 007-scan-experience
intent: 004-card-scanning
phase: inception
status: draft
created: '2026-08-17T13:30:00Z'
updated: '2026-08-17T13:30:00Z'
---

# Unit Brief: scan-experience

## Purpose

The part the collector touches, and the only unit in this intent whose success is measured in seconds
rather than percentages.

Capture a card, crop it on the device, show what it might be, let the user confirm the one thing the
camera cannot see, record the quantity, and stay open for the next card. Then do all of that again in
the browser, identically, as a third entry mode beside the fast-add flow and the set grid.

"Identically" is the design constraint that shapes the unit. FR-21 requires no behavioural divergence
between surfaces, and the cheapest way to guarantee that is **one shared state machine** with two
renderings — the same approach unit 003 takes for the matcher, for the same reason.

The other thing this unit does, almost invisibly, is feed the flywheel. Every confirmation is a label.
Every *correction* is a better label. Capturing them is not a side effect of the flow; it is half the
reason the flow exists.

## Scope

### In Scope
- Camera capture on both surfaces, with on-device card-bounds detection, crop, EXIF strip and bounded
  re-encode
- The candidate list: ranked, capped at 5, each with its calibrated confidence
- Printing confirmation with the most likely pre-selected and finish as the visible field in question
- Recording the confirmed printing — **and any correction** — as a label against the capture
- Add through the existing inventory write path: carry-forward condition, quantity, merge-on-duplicate,
  delta-adjust undo
- "Open card" as an action distinct from "add"
- A batch session: live camera, running tally, per-add undo, offline queue with conflict surfacing
- The web flow as a third entry mode, degrading to file upload where the camera is unavailable

### Out of Scope
- The recogniser (unit 003) — this unit calls it and renders what it returns
- Storing captures (unit 002) — this unit uploads; the service persists
- Any inventory semantic. Scanning is a new **caller** of the existing write path, not a new rule
- Condition inference of any kind, at any confidence
- Sealed product and wishlist. A scanner for booster boxes is a different mechanism and a different
  intent

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-6 | What a scan resolves, and what the user confirms | Must |
| FR-8 | Confirm and record ownership | Must |
| FR-9 | Reach the card from the scan | Must |
| FR-10 | Batch scanning | Should |
| FR-12 | Crop to the card, strip the rest | Must |
| FR-21 | The web camera flow | Must |

---

## Domain Concepts

### Key Entities

| Entity | Description | Attributes |
|--------|-------------|------------|
| ScanSession | An open run of scans with carried state | `session_id`, `condition`, `added[]`, `started_at` |
| CapturedFrame | What the camera produced, after cropping | `bounds`, `bytes`, `long_edge`, `exif_stripped` |
| CandidateSelection | What the user chose from what was offered | `capture_id`, `offered[]`, `chosen_printing_id`, `was_correction` |
| QueuedAdd | An add made without a network | `printing_id`, `condition`, `delta`, `expected_quantity`, `queued_at` |

### Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `capture()` | Frame from the camera | — | raw frame |
| `cropToCard(frame)` | Detect bounds, crop, strip, re-encode | raw frame | captured frame |
| `identify(frame)` | Run the ladder (unit 003) | captured frame | candidates |
| `confirm(candidate, printing)` | Record the user's choice as a label | candidate, printing | selection |
| `add(printing, condition, qty)` | Existing inventory write path | selection | inventory item |
| `undo(add)` | Delta-adjust with `expected_quantity` (ADR-005) | add | result or `409` |
| `reconcile(queue)` | Flush queued adds, surfacing conflicts | queue | applied + conflicts |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 6 |
| Must Have | 5 |
| Should Have | 1 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 033-capture-and-crop | The room never leaves the phone | Must | Planned |
| 034-confirm-printing | Confirm the one thing the camera cannot see | Must | Planned |
| 035-scan-add-to-collection | Scan, confirm, owned | Must | Planned |
| 036-open-card-from-scan | Identifying a card is not the same as owning it | Must | Planned |
| 037-batch-scan-session | A shoebox, not a card | Should | Planned |
| 038-web-camera-entry-mode | The same flow, in a browser, as a third way in | Must | Planned |

---

## Dependencies

### Depends On

| Unit | Reason |
|------|--------|
| 003-identification-engine | Something to call |
| 004-evaluation-and-dataset | **Hard**: the confidences this unit renders must be measured before they are shown |
| 006-mobile-app | A shell to render the mobile half into |
| intent 001 / 003-inventory-core | The inventory write path, merge-on-duplicate, and ADR-005's delta-adjust undo |
| intent 001 / 004-collection-experience | The carry-forward pattern and the add surfaces this becomes a third mode beside |

### Depended By

| Unit | Reason |
|------|--------|
| none | This is the payoff |

### External Dependencies

| System | Purpose | Risk |
|--------|---------|------|
| Device camera | Everything | Medium — permission refusal is a normal path, not an error |
| Browser `getUserMedia` | The web half | Medium — availability varies; file upload is the required fallback |

---

## Technical Context

### Suggested Technology

A shared TypeScript state machine for the flow — capture → identify → confirm → add → next — with two
renderings: React Native components in `mobile/`, MUI components in `frontend/`. The machine holds the
session, the carry-forward condition and the offline queue; the renderings hold nothing but layout.

`expo-camera` on mobile, `getUserMedia` on web. Card-bounds detection runs on-device in both: a
contour/edge pass over a downscaled frame is sufficient for a rectangular card on a contrasting
surface and needs no model.

Optimistic adds with visible revert, reusing the mutation layer intent 001 built for the fast-add flow
rather than inventing a second one.

### Integration Points

| Integration | Type | Protocol |
|-------------|------|----------|
| `scan-api` identify + upload | outbound | HTTPS + platform JWT |
| `elestrals-api` inventory write | outbound | HTTPS + platform JWT |
| `elestrals-api` delta-adjust undo | outbound | HTTPS, ADR-005 contract |
| Device / browser camera | inbound | platform API |

### Data Storage

| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| Session state | in-memory + on-device | small | until the session ends |
| Offline add queue | on-device persistent | tens of items | until reconciled |

---

## Constraints

- **The crop happens before the upload.** The room, the hands and the faces never leave the device.
  The server verifies this; it does not rely on it.
- **Nothing is committed silently.** The pre-selected printing is a suggestion; the add action is the
  user's. This is what makes a "medium confidence" result safe to show at all.
- **A correction is recorded as prominently as a confirmation.** It is the most valuable label the
  system can receive and the easiest one to throw away by only storing the final state.
- **Undo uses the delta-adjust endpoint with `expected_quantity`** (ADR-005) and refuses rather than
  guesses when the holding changed elsewhere. The batch flow fires concurrent requests by design,
  which is precisely the race that ADR exists for.
- **A queued add that conflicts surfaces.** Dropping it silently is the one failure mode a collector
  cannot detect.
- **Condition is never inferred.** Carry-forward is a convenience with a visible current value, not a
  guess about the card.
- **The two surfaces must not diverge.** A difference in behaviour between mobile and web is a defect,
  and the shared state machine is how that is enforced rather than reviewed.
