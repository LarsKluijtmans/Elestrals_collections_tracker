---
id: 038-web-camera-entry-mode
unit: 007-scan-experience
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:35:00Z'
assigned_bolt: 024-scan-experience
implemented: false
---

# Story: 038-web-camera-entry-mode

## User Story

**As** a collector at my desk with a webcam
**I want** to scan cards in the website
**So that** I do not need to install an app to get the feature — and so the two surfaces are one
product rather than two

## Acceptance Criteria

- [ ] **Given** the web app, **When** the add surfaces are used, **Then** scanning appears as a **third
      entry mode** beside the fast-add flow and the set grid
- [ ] **Given** a browser with camera access, **When** scanning starts, **Then** it captures through
      `getUserMedia`
- [ ] **Given** a browser without camera access or with permission refused, **When** scanning starts,
      **Then** it **degrades to file upload** rather than failing
- [ ] **Given** the web flow, **When** it identifies, **Then** it uses the **same `scan-api` endpoint,
      the same candidate shape and the same calibrated confidence** as mobile
- [ ] **Given** a behavioural difference between the two surfaces, **When** it is found, **Then** it is
      treated as a **bug**, not as a platform difference
- [ ] **Given** the browser, **When** on-device text recognition is supported, **Then** pass 1 runs
      locally; otherwise the ladder escalates to the server immediately and **reports which passes ran**
- [ ] **Given** a captured frame in the browser, **When** it is prepared, **Then** cropping and EXIF
      stripping apply **identically** to mobile (story 033)

## Technical Notes

The identical-contract requirement is enforced structurally rather than by review: both surfaces call
the same endpoint and drive the same shared state machine, so there is one behaviour and two
renderings. The MUI layer holds layout and nothing else.

Browser OCR support is the one place the surfaces legitimately differ, and the sixth criterion handles
it honestly — the browser may have no usable on-device text recognition, in which case pass 1 is
skipped and the result **says so** rather than silently behaving differently. Story 004's spike should
report browser capability alongside mobile, so this is known before it is built.

File-upload fallback is not a consolation prize. A user with a good photograph already on disk is a
completely valid path into this feature, and it also makes the flow testable without a camera.

Placing scanning as a third entry mode beside the existing two matters for discoverability: intent
001 built `/collection/add` and `/collection/add/set/:setCode` as the two ways in, and a scan surface
that lives somewhere else entirely will not be found.

## Dependencies

### Requires
- 033-capture-and-crop
- 034-confirm-printing
- 035-scan-add-to-collection
- intent 001 / 016-fast-add-flow and 017-set-grid-entry (implemented) — the surfaces this joins

### Enables
- Nothing — this is a leaf

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| The browser has no camera at all | File upload only, presented as the normal path rather than as a failure |
| The webcam is low-resolution | Identification quality degrades; confidence reflects it honestly. No special-casing |
| The user drags in a non-image file | Rejected client-side with a clear reason |
| Safari behaves differently from Chrome on `getUserMedia` | Handled; the fallback exists precisely because browser camera support is uneven |
| A batch session in a browser tab that is closed | Queued adds persist in browser storage and reconcile on return, matching mobile |
| The on-device matcher package fails to load in the browser | Escalate to the server pass and report that pass 1 did not run — never silently return worse results |

## Out of Scope

- A web batch mode optimised for a webcam-on-a-stand setup — the same session flow applies, but the
  ergonomics of a fixed camera are a separate design question
- Mobile browser scanning, which is neither the app nor the desktop case and is not a target here
