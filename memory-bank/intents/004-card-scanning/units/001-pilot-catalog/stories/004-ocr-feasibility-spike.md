---
id: 004-ocr-feasibility-spike
unit: 001-pilot-catalog
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T13:38:00Z'
assigned_bolt: 018-pilot-catalog
implemented: false
---

# Story: 004-ocr-feasibility-spike

## User Story

**As** the person deciding whether to build six more units
**I want** a measured answer to "can a phone read an Elestrals card?"
**So that** the intent's largest assumption is tested in week one rather than discovered in the week
the scan flow is wired up

## Acceptance Criteria

- [ ] **Given** the evaluation photographs, **When** on-device text recognition runs over them,
      **Then** a per-field read rate is reported for card name, collector number, set code and edition
      stamp
- [ ] **Given** those read rates, **When** they are combined with a fuzzy match against the compiled
      catalog, **Then** an end-to-end top-1 card identification rate is reported
- [ ] **Given** the result, **When** it is written down, **Then** it states the device, the OS text
      recognition API, the image conditions and the sample size alongside the numbers
- [ ] **Given** failures, **When** they are examined, **Then** the dominant failure modes are named and
      counted — glare, sleeve reflection, angle, wear, font, small type
- [ ] **Given** the spike, **When** it concludes, **Then** it produces an explicit **go / no-go /
      go-with-changes** recommendation against the ≥90% top-1 target in NFR §Accuracy
- [ ] **Given** the spike, **When** it is timeboxed, **Then** it stops at the box regardless of result
      and reports what it had

## Technical Notes

This is the analogue of intent 002's bolt-011 source spike and intent 001's bolt-002 catalog spike.
Both were scheduled early for the same reason: they were the places their intents could fail, and
both did in fact change what got built.

The spike runs against ~20 cards first, before story 001 and 002 are complete, and then against the
full evaluation set once they are. Twenty cards is enough to detect a catastrophic result — if the
collector number cannot be read at all, nothing downstream matters and that is knowable in an hour.

Run it on a **mid-range** phone, not a flagship. The performance budget in NFR §Performance is written
for the former.

**What each outcome means:**

| Result | Consequence |
|---|---|
| Top-1 ≥ 90% | Go. The ladder's cheap path carries the product, as designed |
| 70–90% | Go with changes. Pass 1 becomes a filter rather than an answer, and unit 003's server pass carries more weight than planned — with a real cost in latency and upload volume |
| < 70% | **Stop and reconsider.** An OCR-first ladder is the wrong architecture; the intent needs re-cutting around image matching, and FR-3's offline promise cannot be kept |

## Dependencies

### Requires
- 001-compile-pilot-set (partial is sufficient — ~20 cards)
- 002-photograph-reference-set (partial is sufficient)
- 003-held-out-evaluation-set (for the full run)

### Enables
- 012-on-device-text-pass — this spike decides whether that story is worth writing as specified
- 013-identification-ladder — the 90% threshold is validated or revised here
- The whole of units 003, 004 and 007

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Sleeved cards read much worse | Report separately. Sleeves are the normal case for valuable cards, so a sleeve-specific rate is a product fact, not a footnote |
| iOS and Android differ materially | Report both. A divergence here changes what "identical behaviour across surfaces" can mean |
| The browser's OCR options are far weaker than the phone's | Report it. FR-21's web pass may have to escalate to the server immediately, which is allowed and must be stated |
| The result is 89% | Do not round. Report the number and the sample size, and let the go/no-go be a decision someone makes rather than a threshold that quietly passes |

## Out of Scope

- Building the production matcher (story 012)
- Any image matching (story 014) — this spike is text only, deliberately, because text is the cheap
  path whose viability decides the architecture
