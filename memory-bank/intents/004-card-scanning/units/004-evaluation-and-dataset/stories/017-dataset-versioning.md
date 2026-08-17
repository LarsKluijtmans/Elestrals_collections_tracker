---
id: 017-dataset-versioning
unit: 004-evaluation-and-dataset
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:00:00Z'
assigned_bolt: 021-evaluation-harness
implemented: false
---

# Story: 017-dataset-versioning

## User Story

**As** anyone reading an accuracy figure from this project
**I want** that figure to name the data it was measured on
**So that** "90% top-1" is a claim I can check, rather than a number from an unknown moment against an
unknown set

## Acceptance Criteria

- [ ] **Given** the labelled images available, **When** a snapshot is taken, **Then** an immutable
      dataset version is created with a manifest naming every image, its `printing_id`, its label
      provenance and its split side
- [ ] **Given** a frozen version, **When** anything attempts to add or alter an item, **Then** it is
      refused — new data makes a **new version**
- [ ] **Given** a version, **When** its provenance is read, **Then** each item is attributable to
      `own_photo`, `user_confirmed` or `admin_approved`
- [ ] **Given** a version, **When** it is exported, **Then** it produces an archive plus manifest
      usable **outside this codebase**
- [ ] **Given** an accuracy figure anywhere in the system, **When** it is displayed or logged, **Then**
      it names its dataset version
- [ ] **Given** a user deleting their captures, **When** a frozen version referenced those images,
      **Then** the version records the removal without silently changing its historical metrics

## Technical Notes

Version 1 is unit 001's photographs and nothing else — 150-ish images, entirely `own_photo`. That is
enough to calibrate, and it exists before a single user has scanned anything.

Items are stored **by reference**, not by copy: a version is a manifest plus a set of pointers. Copying
2M images per version is not viable and is not necessary, since the images themselves are immutable
once stored.

The export requirement exists because of a decision made at Checkpoint 2: automatic finish detection
and any trained model belong to a **future recogniser-V2 intent**, which may not run inside this
repository. A dataset that can only be read by the service that wrote it would strand that intent
before it starts.

**Deletion versus immutability** is the sharp corner here. A user may delete their captures (story
007) and a frozen version may reference them. The version records the deletion and keeps its computed
metrics — the metric was true when it was computed, and rewriting history to match current data is
precisely what immutability is meant to prevent.

## Dependencies

### Requires
- 002-photograph-reference-set
- 007-capture-store

### Enables
- 018-holdout-split
- 019-accuracy-harness

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A label is later corrected by an admin | The correction lands in the **next** version. The prior version keeps the label it was measured with, flagged as superseded |
| Two versions share most of their images | Normal, and cheap — versions are manifests, not copies |
| An exported archive is huge | Streamed and chunked; export is an offline operation, not a request |
| Someone asks for "current accuracy" with no version named | The question is malformed. Every figure names a version, so the answer is a version's figure |

## Out of Scope

- The split rule (story 018)
- Measuring anything (story 019)
