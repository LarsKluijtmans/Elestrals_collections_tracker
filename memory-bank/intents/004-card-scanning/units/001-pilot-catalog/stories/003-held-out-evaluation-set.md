---
id: 003-held-out-evaluation-set
unit: 001-pilot-catalog
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T13:37:00Z'
assigned_bolt: 018-pilot-catalog
implemented: false
---

# Story: 003-held-out-evaluation-set

## User Story

**As** the person who will publish an accuracy figure
**I want** a set of photographs the matcher has never seen and never will
**So that** "90% top-1 accuracy" is a measurement of recognition rather than a measurement of memory

## Acceptance Criteria

- [ ] **Given** the pilot set, **When** the evaluation shoot completes, **Then** every printing has at
      least one evaluation photograph, taken in a **separate session** from its reference photograph
- [ ] **Given** an evaluation image, **When** the matching corpus is built, **Then** it is not indexed
      — enforced by the `role` column, not by remembering
- [ ] **Given** the two sets, **When** they are compared, **Then** no image appears in both, and no
      *near-duplicate* pair spans them
- [ ] **Given** an evaluation image, **When** its capture conditions are checked, **Then** they differ
      deliberately from the reference shoot — different lighting, angle, background, distance
- [ ] **Given** the manifest, **When** validated, **Then** every evaluation entry carries
      `role = evaluation` and a `printing_id` recorded at capture time

## Technical Notes

Two sessions, not one shoot split in half. A single session produces images that share lighting,
background and camera pose, and a matcher scored against those is being asked an easier question than
a user will ask it.

Deliberate variation is the point: this set exists to be *harder* than the reference set, because the
user's card will be. If evaluation accuracy comes back suspiciously close to 100%, the first thing to
suspect is that the two sets are too similar.

Near-duplicate detection between the sets runs before the split is frozen. Story 018 enforces the
split rule at dataset-version level; this story is where the raw material is kept honest in the first
place.

## Dependencies

### Requires
- 002-photograph-reference-set

### Enables
- 004-ocr-feasibility-spike — the spike measures against this set
- 018-holdout-split
- 019-accuracy-harness

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Only one physical copy of a printing exists | Fine — the same card photographed in a different session is a valid evaluation image. It is the *image* that must be unseen, and the split rule in story 018 additionally holds out by printing |
| A printing has no reference image (uncovered) | It still gets an evaluation image. Measuring what happens on uncovered printings is how `uncovered` gets reported correctly |
| The evaluation set turns out too hard — accuracy near zero | That is a finding, not a broken test. Report it; unit 003 tunes against the reference set, never against this one |
| Someone indexes an evaluation image | Caught by the `role` check in the index build, which fails rather than warns |

## Out of Scope

- The split mechanics and dataset versioning (stories 017, 018)
- Any tuning against these images. Touching this set to improve a number destroys the only thing it
  is for
