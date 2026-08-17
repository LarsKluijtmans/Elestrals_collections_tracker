---
id: 012-on-device-text-pass
unit: 003-identification-engine
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T13:51:00Z'
assigned_bolt: 020-identification-ladder
implemented: false
---

# Story: 012-on-device-text-pass

## User Story

**As** a collector scanning a shoebox
**I want** most cards recognised on my phone without anything being uploaded
**So that** it is fast, it works offline, and my photographs stay mine unless there is a reason for
them not to be

## Acceptance Criteria

- [ ] **Given** a cropped frame, **When** pass 1 runs, **Then** it completes with **no network call**,
      verified in airplane mode
- [ ] **Given** OCR output, **When** it is matched, **Then** the collector number is treated as the
      strongest signal, and where it uniquely determines a card within a set the name serves as
      corroboration rather than as an independent vote
- [ ] **Given** a misread character in a card name, **When** matching runs, **Then** fuzzy matching
      against the closed catalog vocabulary recovers the correct card
- [ ] **Given** the same implementation, **When** it runs in React Native and in the browser, **Then**
      it is literally the same code — one TypeScript package, not two implementations
- [ ] **Given** pass 1, **When** it produces candidates, **Then** each carries a raw score that story
      015 converts to a confidence; pass 1 never invents a percentage of its own
- [ ] **Given** pass 1 on a mid-range phone, **When** it runs, **Then** it completes within 800ms p95
- [ ] **Given** a pass-1 accept, **When** the scan completes, **Then** no image is uploaded **for
      matching** — the capture-corpus upload of story 033 remains a separate, stated action

## Technical Notes

The package takes OCR fields in and returns candidates out. It contains no camera code, no platform
APIs and no network calls, which is what lets it run in React Native, in a browser and in Node under
unit test. The platform-specific part — Apple Vision, MLKit, or a browser OCR — sits outside it and
supplies text.

Matching strategy, in order of signal strength:

1. **Collector number** — a near-unique key, and `UNIQUE (set_id, collector_number)` makes it decisive
   within a set. The denominator (`/126`) also identifies the set on most cards
2. **Set code** — narrows before the name is considered
3. **Name** — normalised edit distance against ~2,700 entries, which is small enough to scan directly

The closed vocabulary is what makes this work at all. OCR on arbitrary text is hard; OCR constrained
to "one of 2,700 known strings" tolerates a surprising amount of noise.

**Story 004's spike decides whether this story survives as written.** If read rates come back between
70% and 90%, pass 1 becomes a filter rather than an answer and the ladder leans on pass 2 — with real
consequences for latency and upload volume. Below 70% and the architecture is wrong.

## Dependencies

### Requires
- 011-catalog-index-for-devices
- 004-ocr-feasibility-spike — which validates or refutes this story's premise

### Enables
- 013-identification-ladder
- 038-web-camera-entry-mode — the same package, in a browser

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| The collector number reads but the name does not | Still a strong candidate. Report which fields were read, so the confidence reflects partial evidence |
| The name reads but the number does not | Weaker — a name can span sets and printings. Candidates include every printing of that name, ranked, rather than a guess at one |
| OCR returns text from the rules box, not the title | Positional filtering: the title occupies a known region. Text from elsewhere is corroboration at best |
| A non-English printing | The language is part of the printing key; a name that matches no English entry is matched against that language's entries rather than folded onto English — the same rule intent 002's matcher applies to listings |
| Nothing readable at all | `no_text_read`, handed to story 016 |

## Out of Scope

- Orchestrating passes (story 013)
- Image matching (story 014)
- Turning a score into a percentage (story 015)
