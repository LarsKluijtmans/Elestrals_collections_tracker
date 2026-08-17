---
unit: 004-evaluation-and-dataset
intent: 004-card-scanning
phase: inception
status: stories-defined
created: '2026-08-17T13:15:00Z'
updated: '2026-08-17T13:15:00Z'
---

# Unit Brief: evaluation-and-dataset

## Purpose

Make FR-5 true.

FR-5 puts a percentage next to a card name. That percentage is a claim about how often the system is
right when it feels this sure — and a claim like that is either measured or invented. This unit is
what measures it: versioned datasets, a held-out split that cannot leak, a harness that reports top-1,
top-3 and calibration, and a gate that refuses to ship an engine change with no recorded run.

It is scheduled before every user-facing surface for exactly that reason. Building the scan flow first
would mean displaying a raw cosine distance dressed as an accuracy figure and retrofitting honesty
afterwards, onto a number users had already been shown.

The unit's second job is quieter and matters later: the dataset it versions is what a future
recogniser-V2 intent trains on. It must therefore be **exportable**, because that intent may not run
inside this codebase.

## Scope

### In Scope
- Immutable dataset versions with a manifest naming every image, label, provenance and split side
- The split rule: held out by **printing and by image**, never indexed into the matching corpus
- The harness: top-1, top-3, per-confidence-band accuracy, and a predicted-versus-actual calibration
  table
- Calibration bands published for unit 003 to consume at request time
- Export of a dataset version for use outside this codebase
- A release gate: no engine change ships without a harness run recorded against it

### Out of Scope
- The engine itself (unit 003)
- Curation — how a capture becomes a *labelled* capture is unit 005's job; this unit consumes labels
  and does not create them
- Training anything. There is no model to train in this intent, by decision
- Dashboards. The harness produces a report; visualising it is not this unit's problem

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-15 | The labelled dataset and the evaluation harness | Must |

---

## Domain Concepts

### Key Entities

| Entity | Description | Attributes |
|--------|-------------|------------|
| DatasetVersion | An immutable snapshot of labelled images | `version`, `created_at`, `image_count`, `printing_count`, `manifest_key`, `frozen` |
| DatasetItem | One labelled image inside a version | `version`, `image_ref`, `printing_id`, `label_provenance`, `split` |
| HarnessRun | One measurement of one engine against one dataset version | `engine`, `engine_ref`, `dataset_version`, `top1`, `top3`, `bands[]`, `ran_at` |
| CalibrationBand | Measured accuracy for a score range | `engine`, `dataset_version`, `score_low`, `score_high`, `measured_accuracy`, `n` |

### Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `snapshot()` | Freeze the current labelled set into a version | labelled captures + unit 001 photographs | dataset version |
| `split(version)` | Assign items to reference or evaluation | dataset version | split assignment |
| `run(engine, version)` | Measure the engine against the held-out slice | engine ref, version | harness run |
| `bands(run)` | Derive calibration bands from a run | harness run | bands published to unit 003 |
| `export(version)` | Emit an archive plus manifest | version | archive |
| `gate(change)` | Refuse an engine change with no recorded run | engine ref | pass / refusal |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 4 |
| Must Have | 4 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 017-dataset-versioning | An accuracy figure that names its data | Must | Planned |
| 018-holdout-split | A split that cannot leak | Must | Planned |
| 019-accuracy-harness | Top-1, top-3, and whether the confidence is honest | Must | Planned |
| 020-release-gate-on-harness | No engine change without a measurement | Must | Planned |

---

## Dependencies

### Depends On

| Unit | Reason |
|------|--------|
| 001-pilot-catalog | The first dataset version is unit 001's photographs; nothing else exists yet |
| 002-scan-service | Captures, labels and somewhere to store versions |
| 003-identification-engine | An engine to measure |

### Depended By

| Unit | Reason |
|------|--------|
| 005-curation-console | Queue ordering uses confidence bands, which must mean something |
| 007-scan-experience | **Hard**: no surface displays a percentage before this exists |

### External Dependencies

| System | Purpose | Risk |
|--------|---------|------|
| CI | Running the harness on an engine change | Low |
| Object storage | Dataset archives and manifests | Low |

---

## Technical Context

### Suggested Technology

Plain Python inside `scan-api`, invoked from a CLI and from CI. No notebook, no separate ML stack —
the harness is a script that loads a manifest, calls the engine, and writes a table. Reports are
markdown plus JSON, committed as build artifacts so an accuracy figure has a history rather than a
current value.

Calibration is a simple binning of raw scores against observed correctness, with counts reported per
band. Sophistication here is not the point; an honest count is.

### Integration Points

| Integration | Type | Protocol |
|-------------|------|----------|
| Engine (unit 003) | inbound call | in-process |
| Object storage | outbound | HTTPS, M2M |
| CI | gate | exit code + report artifact |

### Data Storage

| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| `dataset_versions` | SQL | tens | permanent |
| `dataset_items` | SQL | up to 2M per version, by reference not by copy | permanent |
| `harness_runs` | SQL | hundreds | permanent — this is the accuracy history |
| Archives | object storage | GBs per exported version | on demand |

---

## Constraints

- **A frozen version is frozen.** Adding an image to a published dataset version silently invalidates
  every accuracy figure computed against it. New data makes a new version.
- **The split is by printing as well as by image.** Two photographs of the same card, one in each
  side, makes the matcher look far better than it is — this is the single most common way an
  evaluation lies, and it is easy to do by accident.
- **The evaluation slice is never indexed.** If an evaluation image reaches the matching corpus, the
  measurement becomes a memory test.
- **A band with too few observations reports its `n` and is not displayed as a percentage.** A "94%"
  derived from seventeen samples is a number with no right to that many significant figures.
- **The harness runs from the day unit 001 completes.** There must be no period in which accuracy is
  asserted rather than measured, because that period is exactly when the habit of asserting forms.
- **The gate refuses, it does not warn.** A warning in CI is a thing people learn to scroll past.
