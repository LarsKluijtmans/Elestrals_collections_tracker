---
id: 021-evaluation-harness
unit: 004-evaluation-and-dataset
intent: 004-card-scanning
type: ddd-construction-bolt
status: planned
stories:
  - 017-dataset-versioning
  - 018-holdout-split
  - 019-accuracy-harness
  - 020-release-gate-on-harness
created: 2026-08-17T14:48:00Z

requires_bolts: [018-pilot-catalog, 019-scan-service-foundation, 020-identification-ladder]
enables_bolts: [022-curation-console, 024-scan-experience]
requires_units: [001-pilot-catalog, 002-scan-service, 003-identification-engine]
blocks: false

complexity:
  avg_complexity: 2
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 2
---

## Bolt: 021-evaluation-harness

### Objective

Make the percentages true.

Version the labelled data, split it so it cannot leak, measure top-1, top-3 and calibration against
the held-out slice, publish the confidence bands the engine reads at request time, and gate engine
releases on a recorded run.

**This bolt is the decision point of intent 004.** It is where you find out whether the recogniser is
good enough to put a number in front of a collector.

### Stories Included

- [ ] **017-dataset-versioning**: An accuracy figure that names its data - Priority: Must
- [ ] **018-holdout-split**: A split that cannot leak - Priority: Must
- [ ] **019-accuracy-harness**: Top-1, top-3, and whether the confidence is honest - Priority: Must
- [ ] **020-release-gate-on-harness**: No engine change without a measurement - Priority: Must

### Expected Outputs

- Immutable dataset versions with manifests; version 1 is bolt 018's photographs
- A deterministic split, held out by **printing as well as by image**, with near-duplicate detection
  across the boundary
- A harness reporting top-1, top-3, per-band accuracy and a predicted-versus-actual calibration table,
  with pass/fail against every NFR §Accuracy target
- Published calibration bands consumed by story 015
- An exportable dataset version, for the future recogniser-V2 intent
- A CI gate that **refuses** an unmeasured engine change

### Dependencies

#### Bolt Dependencies (within intent)

- **018-pilot-catalog** (Required): the labelled photographs that make dataset version 1
- **019-scan-service-foundation** (Required): captures, labels, and somewhere to store versions
- **020-identification-ladder** (Required): an engine to measure

#### Unit Dependencies (cross-unit)

- none

#### Enables (other bolts waiting on this)

- 022-curation-console — its queue ordering uses confidence bands
- 024-scan-experience — **hard**: no surface displays a percentage before this bolt

### Notes

**Read the result before planning bolts 22 and 24.** If top-1 lands well below 90%, or calibration is
badly off, the product can still ship — story 015's designed fallback is qualitative bands with no
percentage. But that is a decision to take knowingly here, not a discovery at bolt 24 after users have
seen numbers.

**Splitting by image alone is the trap.** Two photographs of one physical card, one indexed and one
held out, means the matcher is recognising something it has effectively already seen. Accuracy comes
back near-perfect and collapses on contact with users. Holding out by printing as well removes that
path — at the cost of measuring a harder question than production asks, which is why both views are
reported.

**The gate refuses; it does not warn.** This repository has already been burned by a check that
reported clean while silently skipping most of its input — `status-integrity.cjs` scanned 7 of 17 bolt
files for weeks because of CRLF line endings. The lesson recorded then was *a test that silently
checks nothing is worse than no test*. A CI warning is the same failure with extra steps.

**Scope the gate narrowly.** It watches the matcher packages, the fingerprint code and the threshold
configuration. A gate that fires on every commit will be disabled within a month.
