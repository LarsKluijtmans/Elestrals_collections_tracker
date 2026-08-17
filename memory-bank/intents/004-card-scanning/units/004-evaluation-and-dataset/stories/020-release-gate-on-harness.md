---
id: 020-release-gate-on-harness
unit: 004-evaluation-and-dataset
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:03:00Z'
assigned_bolt: 021-evaluation-harness
implemented: false
---

# Story: 020-release-gate-on-harness

## User Story

**As** the person who will not be in the room when someone tweaks a matching threshold on a Friday
**I want** an engine change to be unable to ship without a recorded measurement
**So that** the calibration displayed to users cannot silently become stale, which is worse than
having none because it still looks current

## Acceptance Criteria

- [ ] **Given** a change to the on-device matcher, the server matcher, the fingerprint algorithm or any
      ladder threshold, **When** it is proposed for release, **Then** the gate requires a harness run
      recorded against it
- [ ] **Given** no recorded run, **When** release is attempted, **Then** it is **refused**, not warned
- [ ] **Given** a run whose results fall below the NFR targets, **When** release is attempted, **Then**
      it is refused unless the regression is explicitly acknowledged and recorded
- [ ] **Given** an engine change, **When** it ships, **Then** its calibration bands are republished in
      the same release — engine and calibration never diverge
- [ ] **Given** the gate, **When** it runs in CI, **Then** it produces the harness report as a build
      artifact
- [ ] **Given** a change that does not touch the engine, **When** it is released, **Then** the gate does
      not apply — the trigger is scoped, not blanket

## Technical Notes

The gate refuses rather than warns, deliberately. This repository has already been burned once by a
check that reported clean while silently skipping most of its input — `status-integrity.cjs` scanned 7
of 17 bolt files for weeks because a CRLF working tree defeated its regex, and the story index it
guarded was wrong the whole time. The lesson recorded then was *a test that silently checks nothing is
worse than no test*. A warning in CI is the same failure with extra steps: it is a check people learn
to scroll past.

Scoping matters as much as strictness. If the gate fires on every commit it will be disabled within a
month. It watches the matcher packages, the fingerprint code and the threshold configuration, and
nothing else.

The acknowledged-regression path exists because a deliberate trade — worse top-1, much better latency
— is a legitimate decision. What is not legitimate is making it accidentally. Acknowledgement is
recorded with the release, so the trade is visible later.

## Dependencies

### Requires
- 019-accuracy-harness

### Enables
- Nothing structurally — this story protects everything downstream rather than unblocking it

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A hotfix is needed and the harness takes too long | The acknowledged-regression path is the escape hatch, and it leaves a record. There is no silent bypass |
| Thresholds are configuration and change without a deploy (story 013) | The gate cannot catch a runtime threshold change. So threshold changes are logged with their before-and-after and the next harness run measures them — stated here because it is a real hole in the gate |
| The dataset version changes but the engine does not | Re-run and republish bands. Accuracy is a property of the pair, not of the engine alone |
| CI cannot reach the dataset archive | The gate fails closed. An unmeasurable release is not a releasable one |

## Out of Scope

- What "good enough" is — the NFR targets define it, this story enforces them
- Deployment mechanics beyond the gate itself
