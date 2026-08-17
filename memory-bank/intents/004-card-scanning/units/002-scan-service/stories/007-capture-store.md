---
id: 007-capture-store
unit: 002-scan-service
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T13:42:00Z'
assigned_bolt: 019-scan-service-foundation
implemented: false
---

# Story: 007-capture-store

## User Story

**As** the future version of this recogniser
**I want** every scan retained with what was predicted and what the user actually confirmed
**So that** I can be trained on real Elestrals photographs — which nobody sells, and which only
ordinary use of this product will ever produce

## Acceptance Criteria

- [ ] **Given** any scan attempt, **When** it completes — successfully or not — **Then** a capture row
      exists with its image reference, its passes, its candidates and its outcome
- [ ] **Given** a capture, **When** it is linked, **Then** it points at exactly one printing **or** at
      none. There is no partial, provisional or guessed linkage
- [ ] **Given** a prediction row, **When** it is written, **Then** it records what was actually shown to
      the user, and no later process updates it
- [ ] **Given** a user's confirmation, **When** it is stored, **Then** its provenance is
      `user_confirmed`, distinct from `admin_approved`, and a **correction** is flagged as such
- [ ] **Given** a curation decision, **When** it is made, **Then** it is a new row and never an edit to
      the capture or the prediction
- [ ] **Given** a capture, **When** it is read, **Then** only its owner (`user_sub`) or a caller with
      `elestrals:admin` can retrieve it
- [ ] **Given** a user deleting their captures, **When** the deletion runs, **Then** the image is
      removed and the anonymous outcome counters that accuracy measurement depends on remain

## Technical Notes

Three tables, all append-only in the sense `price_observations` is:

- `scan_captures` — `id`, `user_sub`, `object_key`, dimensions, bytes, `consent_version`, `created_at`
- `scan_predictions` — `capture_id`, `pass_no`, `engine`, `candidates JSON`, `top_confidence`,
  `outcome`, `failure_reason`
- `curation_decisions` — written by unit 005, defined here because it belongs to this schema

Every repository method takes `user_sub` as its first argument, the phase-1 convention that makes
ownership non-optional at the type level rather than a filter someone might forget.

**Why the prediction is frozen.** A displayed prediction is a claim the product made to a person. If a
later model revision could rewrite it, the accuracy history becomes unfalsifiable and the harness in
unit 004 measures nothing. This is the same reasoning that made `price_observations` append-only, and
it applies more strongly here because the claim was shown to a user rather than aggregated away.

Deletion is deliberately partial: the image goes, a row recording "a scan happened, it was correct at
this confidence" stays and carries no user identity. Without that, any user deleting captures silently
edits the measured accuracy of a released engine.

## Dependencies

### Requires
- 006-scan-schema-and-grants

### Enables
- 008-capture-upload-endpoint
- 013-identification-ladder — the ladder writes here
- 017-dataset-versioning
- 021-curation-queue

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| The ladder runs 3 passes | Three prediction rows against one capture, each attributable to its engine |
| A user scans, sees candidates, and abandons without confirming | Capture and predictions stored with outcome `abandoned`. This is a signal about the candidate list, and discarding it loses the only evidence that the UI failed |
| The same physical card is scanned repeatedly in a batch | Each is a separate capture. Deduplication is a curation concern, not a storage one |
| A capture's user is deleted under intent 001's account-deletion path | Captures follow the user; the anonymous counters survive, and the account-deletion job must know that |
| Storage write succeeds, row write fails | The object is orphaned; a sweeper reconciles. Better an orphaned image than a row pointing at nothing |

## Out of Scope

- Validation and re-encoding on the way in (story 008)
- The curation UI and decisions themselves (unit 005)
