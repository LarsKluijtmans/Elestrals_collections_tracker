---
id: 033-capture-and-crop
unit: 007-scan-experience
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:30:00Z'
assigned_bolt: 024-scan-experience
implemented: false
---

# Story: 033-capture-and-crop

## User Story

**As** a collector photographing cards on my kitchen table
**I want** only the card to leave my phone
**So that** the room, my hands and whoever is sitting opposite me are not uploaded as a side effect of
cataloguing a card

## Acceptance Criteria

- [ ] **Given** a camera frame, **When** card bounds are detected, **Then** the detection runs **on the
      device**, before any upload
- [ ] **Given** a detected card, **When** the frame is prepared, **Then** the payload contains the
      **cropped region only**
- [ ] **Given** a frame, **When** it is prepared, **Then** EXIF is stripped and **GPS unconditionally**
- [ ] **Given** a frame whose card bounds cannot be found, **When** the user attempts to proceed,
      **Then** it is **rejected client-side with guidance** — it is not uploaded whole "just in case"
- [ ] **Given** a cropped frame, **When** it is encoded, **Then** it is ≤ 400KB and ≤ 1600px on the long
      edge
- [ ] **Given** the same logic, **When** it runs on mobile and in the browser, **Then** it is the same
      implementation with the same behaviour
- [ ] **Given** the camera, **When** permission is refused, **Then** it is handled as a **normal path**
      with a route forward, not as an error screen

## Technical Notes

Card-bounds detection needs no model. A rectangular card on a contrasting surface is a contour problem:
downscale, edge-detect, find the largest four-sided contour with plausible aspect ratio, perspective-
correct. Cheap enough to run per-frame for a live preview overlay, which doubles as the framing guide
that improves OCR read rates.

**The division of responsibility with story 008 is the important part of this story.** The crop here is
a *privacy* control — it means the data never exists rather than being deleted later, which is the only
form of data protection that cannot fail. The server's validation and re-encode in story 008 is the
*security* boundary, because a modified client can post anything. Both exist; neither substitutes for
the other.

Refusing to upload an unbounded frame is deliberate. The tempting fallback — "send the whole frame and
let the server figure it out" — is precisely how the room ends up on the server.

## Dependencies

### Requires
- 008-capture-upload-endpoint
- 027-expo-app-shell — for the mobile half

### Enables
- 012-on-device-text-pass — which consumes the cropped frame
- 034-confirm-printing
- 038-web-camera-entry-mode

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| The card is on a similarly-coloured surface | Detection fails; the guidance says to move it, rather than uploading a frame nobody can use |
| Several cards are in frame | Largest plausible rectangle wins, with the overlay showing which one. Multi-card capture is not in scope |
| The card is in a sleeve or toploader | Detect the card, not the sleeve, where the difference is visible. Otherwise the sleeve bounds are acceptable — the extra margin is not a privacy problem |
| Camera permission refused | Web falls back to file upload (story 038); mobile explains what the app cannot do and offers the settings deep link |
| A very high-resolution camera | Downscale before encoding; the 400KB ceiling is a requirement, not a target |
| The user uploads a screenshot rather than a photograph | It is an image and it proceeds. It may match perfectly; that is a legitimate use |

## Out of Scope

- Server-side validation (story 008)
- Any identification (unit 003)
