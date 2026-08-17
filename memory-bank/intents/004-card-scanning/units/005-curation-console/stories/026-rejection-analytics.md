---
id: 026-rejection-analytics
unit: 005-curation-console
intent: 004-card-scanning
status: ready
priority: should
created: '2026-08-17T14:15:00Z'
assigned_bolt: 022-curation-console
implemented: false
---

# Story: 026-rejection-analytics

## User Story

**As** the person deciding what to fix next
**I want** rejections and failures grouped and counted
**So that** I can tell the difference between "the matcher is bad" and "we have not photographed those
cards yet" — which look identical from inside a queue of individual rows

## Acceptance Criteria

- [ ] **Given** curation decisions, **When** rejections are aggregated, **Then** they are grouped by
      their closed-enumeration reason and counted
- [ ] **Given** identification failures, **When** they are aggregated, **Then** they are grouped by the
      five reasons from story 016 and counted
- [ ] **Given** the aggregate, **When** it is displayed, **Then** the largest systematic gap is visible
      **without reading individual rows**
- [ ] **Given** relabels, **When** they are aggregated, **Then** the confusion pairs are shown — which
      printing is mistaken for which, and how often
- [ ] **Given** a trend, **When** it is displayed, **Then** it is per source-of-truth over time, so a
      regression after a release is visible as a step change
- [ ] **Given** the analytics, **When** they are accessed, **Then** they require `elestrals:admin`

## Technical Notes

The confusion pairs are the most useful output and the least obvious. If the alt-art printing of one
card is mistaken for its holo printing 40 times, that is a specific, fixable problem — a fingerprint
that does not discriminate on the one region where the two differ. Without pairing, those 40 rows are
40 unremarkable relabels scattered through a queue.

This mirrors intent 002's FR-16, which required the top rejection reasons "grouped and counted, so the
biggest matcher gap is visible without reading rows." The same need appears here for the same reason,
and the phrasing is deliberately parallel — two intents in this project now have a matcher whose
quality has to be judged from aggregates rather than anecdotes.

Prioritised as **Should** because the curation queue works without it. It is what stops curation from
being an endless treadmill, which is a real risk once volume arrives, so it should not slip far.

## Dependencies

### Requires
- 021-curation-queue
- 016-honest-failure-taxonomy

### Enables
- Nothing structurally — it informs unit 003's next iteration and the future V2 intent

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Volumes are tiny at launch | Show counts with their `n` and no percentages. The same discipline as story 015 |
| One card dominates every count because it is popular | Normalise by scan volume per printing as well as showing raw counts; both views answer different questions |
| A reason is used as a catch-all by curators | Visible as a suspiciously large bucket. The closed enumeration should be revised rather than the behaviour tolerated |
| Confusion pairs are asymmetric — A is called B, but B is never called A | Report direction. Asymmetry is a clue about which fingerprint is weak |

## Out of Scope

- Acting on the findings — that is unit 003's work, or the V2 intent's
- General product analytics
