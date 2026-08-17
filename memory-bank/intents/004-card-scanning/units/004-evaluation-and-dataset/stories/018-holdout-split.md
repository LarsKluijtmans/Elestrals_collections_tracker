---
id: 018-holdout-split
unit: 004-evaluation-and-dataset
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:01:00Z'
assigned_bolt: 021-evaluation-harness
implemented: false
---

# Story: 018-holdout-split

## User Story

**As** the person who has to defend an accuracy figure
**I want** the evaluation slice to be impossible to leak into the matching corpus
**So that** the number measures recognition rather than memory — the single most common way an
evaluation quietly lies

## Acceptance Criteria

- [ ] **Given** a dataset version, **When** it is split, **Then** items are assigned to `reference` or
      `evaluation`, and the assignment is recorded in the manifest
- [ ] **Given** the split, **When** it is computed, **Then** it holds out by **printing as well as by
      image** — no printing contributes images to both sides
- [ ] **Given** an evaluation item, **When** the matching index is built, **Then** it is excluded, and
      the build **fails rather than warns** if one is encountered
- [ ] **Given** the two sides, **When** near-duplicate detection runs, **Then** no near-duplicate pair
      spans them
- [ ] **Given** a split, **When** it is regenerated for the same version, **Then** it is deterministic —
      the same version always splits the same way
- [ ] **Given** the split, **When** its coverage is reported, **Then** it states how many printings are
      evaluable at all, since a printing with only one image cannot be on both sides

## Technical Notes

Splitting by image alone is not enough and is the trap worth naming explicitly. Two photographs of the
same physical card, one indexed and one held out, means the matcher is asked to recognise a picture it
has effectively already seen. Accuracy comes back near-perfect and collapses on contact with users.
Splitting by **printing** as well removes that path.

The trade-off is real and should be stated rather than discovered: holding out whole printings means
the matcher is scored on printings it has never been shown, which is *harder* than production, where
most printings are covered. So the harness reports both — accuracy on held-out printings, and accuracy
on held-out images of covered printings — because they answer different questions:

- **Held-out printing**: how does it behave on a card the corpus has never seen? (the `uncovered` path)
- **Held-out image of a covered printing**: how does it behave in normal operation?

Determinism comes from hashing the item id with the version, not from a random seed someone has to
remember.

## Dependencies

### Requires
- 003-held-out-evaluation-set
- 017-dataset-versioning

### Enables
- 019-accuracy-harness
- 009-reference-corpus-and-fingerprints — which must honour the exclusion at build time

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A printing has exactly one image | It cannot be split. Assigned to reference and excluded from the evaluable count, which is reported |
| The pilot set is small enough that holding out printings hurts coverage badly | Report both metrics; do not shrink the holdout to make a number look better. That is the corruption this story exists to prevent |
| Near-duplicate detection flags a legitimate pair (two genuinely different photographs that look alike) | Reviewed by hand at pilot scale; at volume the threshold is tuned and its false-positive rate reported |
| An evaluation image reaches the index anyway | The build fails. Not a warning — a warning here is a silently invalid accuracy figure, and this repo has already learned that lesson once from `status-integrity.cjs` |

## Out of Scope

- Computing metrics (story 019)
- Choosing which images to photograph (unit 001)
