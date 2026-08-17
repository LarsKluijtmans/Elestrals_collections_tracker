---
id: 014-server-image-match
unit: 003-identification-engine
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T13:53:00Z'
assigned_bolt: 020-identification-ladder
implemented: false
---

# Story: 014-server-image-match

## User Story

**As** a collector holding a card that is worn, sleeved, glared or held at an angle
**I want** the app to recognise the *picture* when it cannot read the *words*
**So that** the cards most likely to be valuable — the old, played, sleeved ones — are not the cards
the scanner fails on

## Acceptance Criteria

- [ ] **Given** a cropped frame, **When** pass 2 runs, **Then** it returns ranked printing candidates
      with distances, computed against `printing_fingerprints`
- [ ] **Given** a request, **When** its work budget expires, **Then** it returns the partial candidates
      it has with a stated reason rather than holding the connection open
- [ ] **Given** a corpus of 50k fingerprints, **When** a match runs, **Then** it completes within 1.2s
      p95
- [ ] **Given** a printing with no fingerprint, **When** it is the true answer, **Then** the result
      reports `uncovered_printing` — **not** `no_catalog_match`
- [ ] **Given** the matcher, **When** the fingerprint algorithm changes, **Then** it is a re-index and
      not a data migration
- [ ] **Given** the index, **When** it is used, **Then** no evaluation-role image is in it, enforced at
      build time by story 009

## Technical Notes

Two-stage: perceptual hash to eliminate most of the corpus cheaply, embeddings to rank what survives.
The phash cut is what keeps a linear scan viable at this corpus size.

**Measure before adding a vector index.** 50k rows is small. ADR-002 set this project's precedent when
it chose a tiered SQL scan over FULLTEXT for card search — the simpler mechanism was two orders of
magnitude inside budget, and the complex one brought its own failure modes. If the scan does not hold,
that measurement is the ADR justifying the index.

**`uncovered` versus `not matched` is the important distinction in this story.** They have different
causes and different fixes. `uncovered` means the corpus lacks a fingerprint — fixed by photographing
or curating. `not matched` means the matcher looked at everything it has and found nothing close —
fixed by improving the matcher. Collapsing them hides the corpus's gaps behind the matcher's
reputation, and makes the curation queue's "uncovered printings first" ordering impossible to compute.

CPU work is bounded and runs off the request thread pool so that matching cannot starve the service's
other routes — the reason FR-22 put this in its own service in the first place.

## Dependencies

### Requires
- 008-capture-upload-endpoint
- 009-reference-corpus-and-fingerprints

### Enables
- 013-identification-ladder
- 015-calibrated-confidence

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Two printings share artwork and differ only by an edition stamp | Both returned as candidates within the ambiguity margin. Story 034 asks the user; the matcher does not choose |
| The frame is of the card **back** | All Elestrals card backs are identical, so every fingerprint matches equally. Detect the uniform-back case and return `no_confident_match` with a "turn the card over" hint rather than a list of 50k equally-likely cards |
| A foil card's glare dominates the frame | Fingerprint distance degrades. Report low confidence honestly; this is the case the V2 intent exists to improve |
| The corpus is empty (before unit 001 completes) | Every request is `uncovered_printing`. Correct, and a clear signal rather than a mysterious failure |
| Someone uploads a photo of a different TCG's card | No confident match. This is a normal outcome, not an error path |

## Out of Scope

- Converting a distance into a percentage (story 015)
- Growing the corpus (unit 005)
- Any trained classifier — V1 is classical fingerprints, by decision
