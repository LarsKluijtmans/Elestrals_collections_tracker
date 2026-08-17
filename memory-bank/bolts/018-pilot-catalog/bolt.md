---
id: 018-pilot-catalog
unit: 001-pilot-catalog
intent: 004-card-scanning
type: simple-construction-bolt
status: planned
stories:
  - 001-compile-pilot-set
  - 002-photograph-reference-set
  - 003-held-out-evaluation-set
  - 004-ocr-feasibility-spike
created: 2026-08-17T14:45:00Z

requires_bolts: []
enables_bolts: [019-scan-service-foundation, 020-identification-ladder, 021-evaluation-harness]
requires_units: []
blocks: false

complexity:
  avg_complexity: 2
  avg_uncertainty: 3
  max_dependencies: 2
  testing_scope: 2
---

## Bolt: 018-pilot-catalog

### Objective

Give the intent something to identify, and find out whether it can be identified.

Compile one Elestrals set by hand into the catalog — which is empty today — photograph every printing
in it twice, and measure whether on-device text recognition can read those photographs well enough to
match against a closed catalog.

**This bolt is the go/no-go for intent 004.** Its output is a number, and that number decides whether
the remaining six bolts are worth building as planned.

### Open with a thin slice

Do **not** compile 126 cards and then measure. Compile ~20, photograph them, run the spike, and read
the result before completing the rest. A catastrophic OCR result means the ladder architecture is
wrong, and that is worth an hour of finding out rather than three weeks.

| Spike result | Consequence |
|---|---|
| Top-1 ≥ 90% | **Go.** The ladder's cheap path carries the product as designed |
| 70–90% | **Go with changes.** Pass 1 becomes a filter, not an answer; bolt 020 leans on the server pass, with real latency and upload cost |
| < 70% | **Stop.** An OCR-first ladder is the wrong architecture. Re-cut the intent around image matching and accept that FR-3's offline promise cannot be kept |

### Stories Included

- [ ] **001-compile-pilot-set**: One set, compiled by hand, imported at full coverage - Priority: Must
- [ ] **002-photograph-reference-set**: A reference photograph per printing, labelled as it is taken - Priority: Must
- [ ] **003-held-out-evaluation-set**: A second set of photographs the matcher never sees - Priority: Must
- [ ] **004-ocr-feasibility-spike**: Can a phone read an Elestrals card? - Priority: Must

### Expected Outputs

- The pilot set imported through the **existing** importer at full coverage, replacing the
  `0/126` warning that has stood since bolt 002
- A reference photograph per printing, each labelled with its `printing_id` at capture time
- A held-out evaluation set, disjoint by printing and by image
- A capture manifest binding every image to a printing and a role
- A written spike report: per-field read rates, end-to-end top-1, dominant failure modes, device and
  conditions, and an explicit go / no-go / go-with-changes recommendation

### Dependencies

#### Bolt Dependencies (within intent)

- none — this is the first bolt of the intent

#### Unit Dependencies (cross-unit)

- **intent 001 / 002-card-catalog**: the importer, normaliser and catalog schema. Implemented; this
  bolt adds data, not code

#### Enables (other bolts waiting on this)

- 019-scan-service-foundation
- 020-identification-ladder
- 021-evaluation-harness

### Notes

**No code changes to the importer.** If the pilot set cannot be expressed in the existing CSV shape,
that is a finding about the catalog schema and belongs in a decision record — not an ad-hoc column.

**Labels are written at capture time.** A photograph labelled afterwards from memory is a guess, and a
guessed label corrupts both the corpus and every accuracy figure later computed against it. This is
the single most important discipline in the bolt and the easiest one to let slide at card 90.

**Photograph under realistic conditions** — handheld, indoor light, no lightbox. A lightbox corpus
measured against lightbox evaluation images yields an accuracy figure that does not survive a kitchen
table, and it is believed because it is high.

The pilot set is assumed to be FE01 because that is the file that exists. **If another set is owned
more completely, use it** — every printing must be physically photographed, and a set with holes
produces a corpus with holes.
