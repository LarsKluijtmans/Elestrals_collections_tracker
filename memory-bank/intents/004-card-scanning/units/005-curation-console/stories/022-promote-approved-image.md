---
id: 022-promote-approved-image
unit: 005-curation-console
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:11:00Z'
assigned_bolt: 022-curation-console
implemented: false
---

# Story: 022-promote-approved-image

## User Story

**As** a collector browsing the catalog
**I want** to see a picture of the card
**So that** the card pages stop being text — which is what they have been since launch, because the
catalog stores image URLs and has never had one

## Acceptance Criteria

- [ ] **Given** an approved capture, **When** an admin promotes it, **Then** it becomes the display
      image for that printing, and exactly one display image exists per printing
- [ ] **Given** a display image, **When** it is replaced, **Then** the replacement is also an explicit
      admin action and the previous one is superseded rather than deleted from the record
- [ ] **Given** promotion, **When** it happens, **Then** it is **never automatic**, at any confidence —
      a technically correct match can still be an unusable photograph
- [ ] **Given** a promoted image, **When** it is served, **Then** it comes from storage-api on an
      **immutable object key**
- [ ] **Given** a promoted image, **When** the contributor's preference is applied, **Then** they are
      credited or anonymous **by their own choice**
- [ ] **Given** a printing with a seeded reference image, **When** a capture for it is promoted,
      **Then** the seeded image is deleted and its fingerprint rebuilt from the approved capture
- [ ] **Given** a printing with no approved image, **When** its card page renders, **Then** it shows the
      existing honest empty state rather than a placeholder implying accidental absence

## Technical Notes

This story is where the data model's image-rights note finally resolves, by a route nobody planned: not
by obtaining permission from the publisher, but by using photographs our own users took, gated on an
admin's approval.

**The exposure is real and was accepted deliberately on 2026-08-17.** A collector's photograph of a
card contains the publisher's artwork; displaying it publicly is a reproduction regardless of who held
the camera. The decision was yes, *conditional on admin approval* — which is what makes it a reviewed
act rather than an automatic one, and it is the condition this story implements. The accepted risk,
its owner and its review triggers belong in an ADR alongside story 010's.

The seeded-image replacement in the sixth criterion is what makes FR-16's "bounded and shrinking"
literal: every promotion here removes one cached image from story 010's count.

## Dependencies

### Requires
- 021-curation-queue
- 009-reference-corpus-and-fingerprints
- 010-seeded-images-bounded

### Enables
- 023-published-image-projection
- 034-confirm-printing — candidate lists with pictures are considerably more useful than candidate
  lists with names

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Several good captures exist for one printing | One is the display image; the rest remain in the corpus as fingerprints. Being the display image is a presentation role, not a quality ranking |
| The contributor later deletes their account | The image's display status follows their consent (story 025), not their account. If display consent was given and not withdrawn, the credit becomes anonymous rather than the image disappearing — and this behaviour must be stated in the consent text |
| An approved image turns out to be a counterfeit card | Withdraw it. A separate reason from "wrong printing", because it says something about the card rather than the photograph |
| Promotion while the projection is refreshing | The projection is refreshed on decision; a partial state is never readable because the read is a single-table select of published rows |

## Out of Scope

- The projection mechanics (story 023)
- Rendering on `/cards/:id` — the collection backend already has card-detail code and reads the
  projection
