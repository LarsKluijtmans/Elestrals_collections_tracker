---
id: 013-identification-ladder
unit: 003-identification-engine
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T13:52:00Z'
assigned_bolt: 020-identification-ladder
implemented: false
---

# Story: 013-identification-ladder

## User Story

**As** a collector
**I want** the app to try harder only when it needs to
**So that** an easy card is instant and a hard card still gets answered — without the app spending
three seconds and my data allowance on a card it recognised immediately

## Acceptance Criteria

- [ ] **Given** pass 1 returning a candidate at or above the accept threshold, **When** the ladder
      evaluates it, **Then** it stops immediately and no further pass runs
- [ ] **Given** any identification attempt, **When** it runs to completion, **Then** it has performed
      **at most 3 passes**
- [ ] **Given** a pass that would re-ask an identical question against identical input, **When** the
      ladder considers it, **Then** it is **skipped rather than run** — passes 2 and 3 must differ by
      frame or by hint
- [ ] **Given** the ladder, **When** its wall-clock budget expires, **Then** it returns the best
      candidate it has with terminal reason `timed_out`, rather than continuing
- [ ] **Given** a completed ladder, **When** its record is read, **Then** every pass names the engine
      that produced it, so any result is attributable
- [ ] **Given** the accept threshold, **When** it is changed, **Then** it takes effect with **no
      deploy** — it is configuration, not a literal
- [ ] **Given** `scan-api` unreachable, **When** the ladder runs, **Then** it completes with pass 1
      only, states that it degraded, and does not block the add

## Technical Notes

The ladder is the story that encodes the user's own design: *"first try the on-device AI, then the
server one for a double check, max 3 times, pick the best; if the first is more than 90% sure just go
with that."*

Two conditions were added that the design did not state, because without them "three tries" is not
worth having:

**Passes must differ.** Re-running an identical engine over an identical frame returns an identical
answer. Pass 2 escalates engine; pass 3 must bring a **new frame** (the camera has kept shooting) or a
**hint** from earlier passes — for example, a set narrowed by a partially-read collector number, which
turns a whole-catalog search into a 126-card one.

**The ladder has a ceiling.** 2.5s p95 for the worst case. Three sequential passes each taking their
time is how a feature that works becomes a feature nobody uses.

Thresholds — accept, reject floor, ambiguity margin — all live in configuration. The 90% accept
threshold is the user's stated number and story 019 will report whether it is the right one; if the
measured false-accept rate at 90% exceeds the 2% target, the threshold moves, and it must move without
a release.

## Dependencies

### Requires
- 007-capture-store
- 012-on-device-text-pass
- 014-server-image-match

### Enables
- 015-calibrated-confidence
- 016-honest-failure-taxonomy
- 034-confirm-printing
- 037-batch-scan-session

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Pass 1 is at 89% and the threshold is 90% | Escalates. The threshold is a threshold; near-misses are exactly what pass 2 exists for |
| Pass 2 returns a *worse* candidate than pass 1 | The best across all passes wins, not the last. "Pick the best one we think has the highest chance" is the stated intent |
| No second frame is available for pass 3 | Pass 3 is skipped rather than run on a stale frame. Two passes is a complete ladder |
| Pass 2 times out but pass 1 had a candidate | Return pass 1's candidate with `timed_out` noted. Something honest beats nothing |
| The user cancels mid-ladder | Passes stop; the capture and whatever predictions exist are still recorded with outcome `abandoned` |
| Upload succeeds, matching fails | Distinguish the two in the record — an upload problem and a matching problem have different fixes |

## Out of Scope

- What the candidates look like on screen (unit 007)
- Deciding whether the threshold is correct (story 019 measures it; this story makes it changeable)
