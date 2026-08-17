---
id: 015-calibrated-confidence
unit: 003-identification-engine
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T13:54:00Z'
assigned_bolt: 020-identification-ladder
implemented: false
---

# Story: 015-calibrated-confidence

## User Story

**As** a collector deciding whether to trust "94%"
**I want** that number to mean "when it says 94%, it is right about 94% of the time"
**So that** I can act on it — which is the only thing a percentage is for, and the only thing that
makes showing one defensible

## Acceptance Criteria

- [ ] **Given** a raw engine score, **When** a confidence is displayed, **Then** it is the **measured
      accuracy** of that engine in that score band on the evaluation set — never the raw score itself
- [ ] **Given** a displayed confidence, **When** it is compared against measured accuracy in its band,
      **Then** the two agree within ±10 percentage points
- [ ] **Given** a score band with too few observations, **When** a result falls in it, **Then** it is
      **not** rendered as a percentage; a qualitative band is shown instead, with its `n` available
- [ ] **Given** a candidate list, **When** it is returned, **Then** it is ordered by confidence and
      capped at 5
- [ ] **Given** two candidates within the ambiguity margin, **When** the result renders, **Then** it is
      presented as a **choice**, not as a top answer with an alternative beneath it
- [ ] **Given** a candidate, **When** it is shown, **Then** it names the card, the set and the printing
      attributes it is asserting, so the user knows what they are confirming
- [ ] **Given** a confidence, **When** it is rendered, **Then** it uses the existing confidence
      component from intent 002, so a scan confidence and a price confidence read alike

## Technical Notes

This is the story that makes FR-5 honest, and it has a hard dependency on unit 004 that is worth being
explicit about: **without a harness run, this story cannot produce a number.** Its fallback is not a
guess — it is showing a qualitative band and no percentage at all. That fallback is the correct
behaviour before the first harness run, and it must be the shipped behaviour rather than a temporary
placeholder that acquires a hardcoded number.

Calibration bands come from story 019, keyed by engine and dataset version. Each is a score range with
a measured accuracy and an observation count. At request time this is a lookup, not a computation.

**The ambiguity margin is a separate control from the accept threshold.** A result can be 92%
confident and still ambiguous, when the second candidate is at 88%. Presenting that as an answer with
a footnote invites a wrong confirmation; presenting it as a choice costs one tap and is honest.

This project has now refused three times to display a number it had not earned: FR-4's sold-versus-
listed split, the `ConfidencePill` as a required prop, and this. The consistency is the point — a
product that is careful about numbers in one place and casual in another has not actually decided
anything.

## Dependencies

### Requires
- 013-identification-ladder
- 019-accuracy-harness — **hard dependency for the numeric form**

### Enables
- 034-confirm-printing
- 021-curation-queue — its ordering uses confidence bands

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| No harness run exists yet | Qualitative bands only. No percentage is displayed. Not a placeholder number |
| The engine changes but the bands do not | Story 020's release gate refuses the change. Stale calibration is worse than none because it looks current |
| A band's measured accuracy is 100% on 12 samples | Not displayed as 100%. Report the band with its `n`; certainty from twelve samples is not certainty |
| The top candidate is above the accept threshold but the second is within the margin | Choice, not answer. The threshold governs *stopping the ladder*; the margin governs *how it is presented* |
| Calibration drifts as the corpus grows | Expected. Bands are versioned with the dataset, and drift between versions is itself a reportable signal |

## Out of Scope

- Producing the measurements (unit 004)
- Rendering the choice UI (story 034)
