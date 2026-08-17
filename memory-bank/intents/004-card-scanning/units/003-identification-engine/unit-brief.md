---
unit: 003-identification-engine
intent: 004-card-scanning
phase: inception
status: draft
created: '2026-08-17T13:10:00Z'
updated: '2026-08-17T13:10:00Z'
---

# Unit Brief: identification-engine

## Purpose

The recogniser. Given a cropped frame, produce a ranked list of candidate printings, each with a
confidence a collector can act on — or say honestly that there is no confident match.

The design decision that shapes the whole unit is the **ladder**: try cheaply on the device first, and
escalate only when the cheap answer is not good enough. A card read correctly by on-device OCR costs
no upload, no server time, no network, and works in a shop with no signal. Escalation is the exception
path, not the default.

The second decision is that the on-device matcher is **one shared TypeScript implementation** consumed
by both React Native and the browser. FR-21 requires the two surfaces to behave identically; the
cheapest way to guarantee that is for there to be only one implementation to disagree with.

## Scope

### In Scope
- A versioned, delta-updatable catalog index for on-device matching, with staleness detection
- The on-device text pass: OCR output → fuzzy match against the closed catalog vocabulary
- Ladder orchestration: ≤3 passes, 90% short-circuit, distinct frame or hint per pass, wall-clock
  budget, per-pass attribution
- The server image pass: phash + embedding nearest neighbour over `printing_fingerprints`
- The calibration layer: raw score → measured confidence band
- The failure taxonomy and the search fallback

### Out of Scope
- Camera capture, cropping and the confirmation UI (unit 007) — this unit takes a cropped frame and
  returns candidates
- Measuring how good any of it is (unit 004) — this unit *consumes* calibration bands, it does not
  produce them
- Automatic finish detection. Deferred to a future recogniser-V2 intent by decision
- Training any model. V1 uses classical fingerprints and platform OCR; there is nothing to train on
  until the flywheel has turned

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-2 | The identification ladder | Must |
| FR-3 | On-device pass — text recognition, offline | Must |
| FR-4 | Server pass — image match against the reference corpus | Must |
| FR-5 | Ranked candidates with calibrated confidence | Must |
| FR-7 | Honest failure, with a way forward | Must |

---

## Domain Concepts

### Key Entities

| Entity | Description | Attributes |
|--------|-------------|------------|
| CatalogIndex | The compact catalog a device matches text against | `version`, `built_at`, `entries`, `bytes`, `delta_from` |
| LadderRun | One identification attempt, across up to three passes | `capture_id`, `passes[]`, `elapsed_ms`, `terminal_reason` |
| Pass | One attempt by one engine | `pass_no`, `engine`, `input_ref`, `candidates[]`, `elapsed_ms` |
| Candidate | One possible answer | `printing_id`, `card_id`, `raw_score`, `confidence`, `asserted_attributes` |
| FailureReason | Why nothing was returned | one of `no_text_read`, `no_catalog_match`, `uncovered_printing`, `below_floor`, `timed_out` |

### Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `index.build()` | Compact the catalog for on-device use | catalog | index blob + version |
| `textPass(ocr, index)` | Fuzzy-match read text to catalog entries | OCR fields, index | candidates |
| `ladder.run(frames)` | Orchestrate up to three passes with early exit | frames, thresholds | ladder run |
| `imagePass(frame)` | Nearest neighbour over fingerprints | cropped frame | candidates + distances |
| `calibrate(engine, score)` | Convert a score into a measured confidence | engine, raw score, bands | confidence |
| `classifyFailure(run)` | Name why nothing matched | ladder run | failure reason |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 6 |
| Must Have | 6 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 011-catalog-index-for-devices | A catalog small enough to carry | Must | Planned |
| 012-on-device-text-pass | Read the card, match the text, stay offline | Must | Planned |
| 013-identification-ladder | Try cheaply, escalate deliberately, stop early | Must | Planned |
| 014-server-image-match | Match the picture when the words fail | Must | Planned |
| 015-calibrated-confidence | A percentage that means what it says | Must | Planned |
| 016-honest-failure-taxonomy | Say "I don't know", and say why | Must | Planned |

---

## Dependencies

### Depends On

| Unit | Reason |
|------|--------|
| 001-pilot-catalog | A populated catalog to index, and a corpus to match against |
| 002-scan-service | Somewhere to run, fingerprints to read, predictions to record |

### Depended By

| Unit | Reason |
|------|--------|
| 004-evaluation-and-dataset | There is nothing to measure without an engine |
| 007-scan-experience | The surfaces call this unit and render what it returns |

### External Dependencies

| System | Purpose | Risk |
|--------|---------|------|
| Platform OCR (Apple Vision / MLKit) | The on-device text pass | **Medium** — measured in unit 001's spike before this unit starts, which is the point of scheduling it there |
| Embedding model | Server-side image match | Medium — must run on CPU inside the latency budget; a model too heavy to serve is a design constraint, not a tuning problem |

---

## Technical Context

### Suggested Technology

The on-device matcher is a plain TypeScript package with no platform APIs in it — OCR text in,
candidates out — so it runs unchanged in React Native and the browser and is unit-testable in Node.
Fuzzy matching over a closed vocabulary of ~2,700 names: normalised edit distance with a
collector-number-first strategy, since the number is the strongest signal on the card.

Server-side: perceptual hash for a cheap first cut, embeddings for the ranking. At 50k fingerprints a
linear scan is plausibly inside budget — **measure before introducing a vector index**, the same
reasoning ADR-002 applied when it chose a tiered SQL scan over FULLTEXT for card search.

### Integration Points

| Integration | Type | Protocol |
|-------------|------|----------|
| `printing_fingerprints` | inbound read | SQLAlchemy within `scan-api` |
| Catalog index endpoint | outbound | HTTPS, cacheable, versioned |
| Identification endpoint | inbound | HTTPS, platform JWT |
| Calibration bands | inbound | produced by unit 004, read at request time |

### Data Storage

| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| Catalog index blobs | object storage | ≤8MB per version | last few versions |
| Calibration bands | SQL | tens of rows per engine per dataset version | permanent |

---

## Constraints

- **Pass 1 must complete with no network.** Offline is the normal case for a scanner, not a degraded
  one.
- **A pass that would re-ask an identical question against identical input is skipped, not run.**
  Otherwise "up to three attempts" is one attempt billed three times.
- **The ladder has a wall-clock ceiling.** Three passes that each take their time is a broken-feeling
  app; the budget is the requirement, and exceeding it returns the best candidate so far with
  `timed_out`.
- **A raw score is never displayed.** Calibration is a hard dependency of display, which is why unit
  004 is scheduled before any surface.
- **`uncovered` and `not_matched` are different answers.** One means the corpus has no fingerprint for
  that printing; the other means the matcher looked and failed. Collapsing them hides the corpus's
  gaps behind the matcher's reputation.
- **The confidence floor rejects rather than guesses.** A ranked list of noise is worse than "no
  confident match", because it invites a wrong add that nobody will notice until valuation looks odd.
