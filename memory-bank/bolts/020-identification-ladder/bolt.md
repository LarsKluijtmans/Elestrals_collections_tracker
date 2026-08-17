---
id: 020-identification-ladder
unit: 003-identification-engine
intent: 004-card-scanning
type: ddd-construction-bolt
status: planned
stories:
  - 011-catalog-index-for-devices
  - 012-on-device-text-pass
  - 013-identification-ladder
  - 014-server-image-match
  - 015-calibrated-confidence
  - 016-honest-failure-taxonomy
created: 2026-08-17T14:47:00Z

requires_bolts: [018-pilot-catalog, 019-scan-service-foundation]
enables_bolts: [021-evaluation-harness, 024-scan-experience]
requires_units: [001-pilot-catalog, 002-scan-service]
blocks: false

complexity:
  avg_complexity: 3
  avg_uncertainty: 3
  max_dependencies: 3
  testing_scope: 3
---

## Bolt: 020-identification-ladder

### Objective

Build the recogniser: a cropped frame in, ranked candidate printings out, each with a confidence a
collector can act on — or an honest refusal.

The shape is the ladder the user specified: **try cheaply on the device, stop at 90%, escalate only
when needed, never more than three passes.** Two conditions were added at inception that the design
did not state and without which "three tries" is not worth having — passes must differ by frame or
hint, and the whole ladder has a wall-clock ceiling.

### Stories Included

- [ ] **011-catalog-index-for-devices**: A catalog small enough to carry - Priority: Must
- [ ] **012-on-device-text-pass**: Read the card, match the text, stay offline - Priority: Must
- [ ] **013-identification-ladder**: Try cheaply, escalate deliberately, stop early - Priority: Must
- [ ] **014-server-image-match**: Match the picture when the words fail - Priority: Must
- [ ] **015-calibrated-confidence**: A percentage that means what it says - Priority: Must
- [ ] **016-honest-failure-taxonomy**: Say "I don't know", and say why - Priority: Must

### Expected Outputs

- A versioned, delta-updatable catalog index (≤8MB) with staleness detection
- A **shared TypeScript** on-device matcher — one package consumed by React Native, the browser and
  Node tests, so the two surfaces cannot diverge
- Ladder orchestration with configurable thresholds, per-pass attribution and a wall-clock budget
- Server image match: phash + embedding nearest neighbour, `uncovered` distinguished from `not_matched`
- Calibration lookup mapping raw scores to measured confidence bands — with its designed fallback of
  qualitative bands when no harness run exists yet
- The five failure reasons, counted separately, with a pre-filled search fallback

### Dependencies

#### Bolt Dependencies (within intent)

- **018-pilot-catalog** (Required): a corpus to match against, and the spike that validated pass 1
- **019-scan-service-foundation** (Required): somewhere to run, fingerprints to read, predictions to
  record

#### Unit Dependencies (cross-unit)

- **intent 001 / 002-card-catalog**: the catalog the index projects from, and `UNIQUE (set_id,
  collector_number)` — the constraint the collector-number-first matching strategy rests on

#### Enables (other bolts waiting on this)

- 021-evaluation-harness
- 024-scan-experience

### Notes

**Uncertainty 3, and the reason is upstream.** Bolt 018's spike will already have told us whether pass
1 works. What remains uncertain here is pass 2 — whether a cropped handheld photograph fingerprints
well enough to rank correctly against 50k entries. That is not knowable until bolt 021 measures it,
which is why bolt 021 follows immediately.

**No percentage ships from this bolt alone.** Story 015's numeric form has a hard dependency on the
harness in bolt 021. Its correct behaviour before then is qualitative bands and no percentage — and
that must be the shipped fallback, not a placeholder that quietly acquires a hardcoded number.

**`uncovered` versus `not_matched` is not a detail.** They have different causes and different fixes,
and collapsing them hides the corpus's gaps behind the matcher's reputation. Bolt 022's queue ordering
cannot be computed without the distinction.

**Thresholds are configuration.** The 90% accept threshold is the user's stated number; bolt 021 will
report whether it holds. If the measured false-accept rate exceeds 2%, the threshold moves — and it
must move without a release.
