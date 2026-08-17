---
id: 019-accuracy-harness
unit: 004-evaluation-and-dataset
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:02:00Z'
assigned_bolt: 021-evaluation-harness
implemented: false
---

# Story: 019-accuracy-harness

## User Story

**As** the person about to show a collector a percentage
**I want** a repeatable measurement of how often the engine is right at each confidence level
**So that** the percentage is a measurement rather than a decoration, and so that a change to the
engine can be shown to have helped

## Acceptance Criteria

- [ ] **Given** an engine and a dataset version, **When** the harness runs, **Then** it reports **top-1
      and top-3 accuracy**, overall and per confidence band
- [ ] **Given** a run, **When** calibration is computed, **Then** it produces a predicted-versus-actual
      table with an observation count per band
- [ ] **Given** a run, **When** it completes, **Then** it publishes calibration bands that story 015
      consumes at request time
- [ ] **Given** a run, **When** it is recorded, **Then** it names the engine reference, the index
      version and the dataset version — a figure with no provenance is not stored
- [ ] **Given** the NFR targets, **When** a run completes, **Then** it states pass or fail against each:
      top-1 ≥ 90%, top-3 ≥ 98%, calibration within ±10pp, false confident accept ≤ 2%
- [ ] **Given** unit 001's completion, **When** the harness first runs, **Then** it runs on the pilot
      set — there is no period in which accuracy is asserted rather than measured
- [ ] **Given** a band with too few observations, **When** it is reported, **Then** its `n` is stated
      and it is not published as a displayable percentage

## Technical Notes

A script, not a platform. Load a manifest, call the engine, tabulate. Output is markdown plus JSON,
kept as build artifacts so accuracy has a *history* rather than a current value — the trend across
dataset versions is more informative than any single figure.

The **false confident accept** rate is the metric that matters most for product safety, and it is the
one that decides whether the user's 90% threshold is right. If more than 2% of ≥90% accepts are wrong,
the threshold moves. Story 013 made it configuration precisely so that this measurement can act on it
without a release.

Reporting both split views from story 018 — held-out printings and held-out images of covered
printings — keeps the `uncovered` path honest. A matcher can look excellent on covered printings and
be useless on new ones, and only one of those numbers predicts what happens when a user scans a set
nobody has photographed.

## Dependencies

### Requires
- 018-holdout-split
- 013-identification-ladder
- 014-server-image-match

### Enables
- 015-calibrated-confidence — **hard**: this is where its numbers come from
- 020-release-gate-on-harness
- 021-curation-queue

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Accuracy is below target | Reported as a failure against the NFR, plainly. This is the harness working, and it is better than the alternative of finding out from users |
| The engine is non-deterministic | Fix that first. A recogniser whose answer varies between runs cannot be calibrated at all |
| A dataset version is too small for per-band figures | Report overall accuracy and state which bands lack observations; do not interpolate |
| Two engines are compared | Same dataset version or the comparison is meaningless, and the harness refuses a cross-version comparison |
| Running the harness takes hours as the corpus grows | Sample deterministically and report the sample size. A slow harness gets skipped, and a skipped harness is the failure mode this whole unit exists to prevent |

## Out of Scope

- Fixing accuracy — this story measures, unit 003 improves
- Dashboards; the report is a file
