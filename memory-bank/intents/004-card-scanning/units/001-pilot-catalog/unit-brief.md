---
unit: 001-pilot-catalog
intent: 004-card-scanning
phase: inception
status: draft
created: '2026-08-17T13:00:00Z'
updated: '2026-08-17T13:00:00Z'
---

# Unit Brief: pilot-catalog

## Purpose

Give the intent something to identify, and find out whether it can be identified.

`backend/data/catalog/FE01.csv` ships with a header and no rows — deliberately, because ADR-001 found
that the one complete public source prohibits both scraping and reproduction. Every downstream unit in
this intent assumes a populated catalog and a corpus of reference images. Neither exists.

This unit produces both, for **one set**, and then asks the question that decides whether the other
six units are worth building: **can on-device text recognition read an Elestrals card well enough to
match it against a closed catalog?** That number is the output of this unit that matters most. The
photographs are the second.

## Scope

### In Scope
- Compiling one pilot set by hand into CSV rows, one row per printing, through the **existing**
  importer and its existing normaliser
- Photographing every printing in that set under conditions a collector would actually reproduce —
  handheld, indoor light, no lightbox
- A second, disjoint set of photographs held out for evaluation
- A capture manifest binding each photograph to its `printing_id` at the moment it is taken
- A timeboxed spike measuring on-device OCR read rates on those photographs

### Out of Scope
- Any other set. Coverage beyond the pilot is a data problem this intent deliberately does not solve
- Any change to the importer, the normaliser or the catalog schema — if the pilot set needs one, that
  is a finding, not a task
- Fingerprints and the corpus index (unit 002 owns the storage, unit 003 the matching)
- Card images displayed anywhere (unit 005)

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | A pilot catalog with reference photographs | Must |

---

## Domain Concepts

### Key Entities

| Entity | Description | Attributes |
|--------|-------------|------------|
| PilotSet | The one set compiled by hand | `set_code`, `card_count`, compiled coverage |
| ReferencePhotograph | An image of a known printing, taken by us, indexed by the matcher | `printing_id`, `file`, `captured_at`, `conditions`, `role = reference` |
| EvaluationPhotograph | An image of a known printing, **never indexed**, used only to measure | `printing_id`, `file`, `role = evaluation` |
| CaptureManifest | The binding of file to printing, written at capture time | `printing_id`, `file`, `role`, `notes` |

### Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `import(FE01.csv)` | Existing importer, unchanged | CSV rows | coverage report `n/126` |
| `manifest.record(file, printing)` | Bind an image to a printing as it is taken | file, printing id, role | manifest row |
| `spike.measure(photos)` | Read rate of name, collector number, set code | photographs | per-field read rate + failure modes |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 4 |
| Must Have | 4 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 001-compile-pilot-set | One set, compiled by hand, imported at full coverage | Must | Planned |
| 002-photograph-reference-set | A reference photograph per printing, labelled as it is taken | Must | Planned |
| 003-held-out-evaluation-set | A second set of photographs the matcher never sees | Must | Planned |
| 004-ocr-feasibility-spike | Can a phone read an Elestrals card? — the go/no-go | Must | Planned |

---

## Dependencies

### Depends On

| Unit | Reason |
|------|--------|
| intent 001 / 002-card-catalog | The importer, the normaliser, `sets`/`cards`/`printings`. This unit adds data, not code |

### Depended By

| Unit | Reason |
|------|--------|
| 002, 003, 004, 005, 007 | There is nothing to identify, fingerprint, measure, curate or display without it |

### External Dependencies

| System | Purpose | Risk |
|--------|---------|------|
| Physical cards | The set must be physically present to be photographed | **Medium** — a set you own completely is worth more than the first set numerically. Open question |
| A phone camera | The spike must run on the class of device the product targets | Low |

---

## Technical Context

### Suggested Technology

No new technology. CSV through `backend/app/importer/sources/csv_seed.py`, unchanged. The spike runs
on-device text recognition — Apple Vision on iOS, MLKit on Android — through an Expo dev build, or a
thin harness app if the mobile shell does not yet exist. The spike's output is a table of read rates,
not a library.

### Integration Points

| Integration | Type | Protocol |
|-------------|------|----------|
| Existing catalog importer | inbound | CSV file on disk |
| Photograph storage | local | files + a manifest, versioned with the repo or in object storage — decided in story 002 |

### Data Storage

| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| Pilot set rows | SQL (`elestrals`) | ~126 cards, ~150 printings | permanent |
| Reference photographs | files | ~150 images | permanent — this is the corpus seed |
| Evaluation photographs | files | ~150 images | permanent — accuracy history depends on stability |

---

## Constraints

- **The importer does not change.** If the pilot set cannot be expressed in the existing CSV shape,
  that is a finding about the catalog schema and belongs in a decision record, not in an ad-hoc column.
- **Labels are written at capture time.** A photograph labelled afterwards from memory is a guess, and
  a guessed label poisons both the corpus and every accuracy figure computed against it. This is the
  single most important discipline in the unit.
- **Reference and evaluation sets are disjoint by printing *and* by image.** Photographing the same
  card twice and putting one image in each set makes the matcher look far better than it is.
- **Photographs are taken under realistic conditions.** A lightbox corpus measured against lightbox
  evaluation images produces an accuracy number that does not survive contact with a kitchen table.
- **The spike is timeboxed and its result is written down whatever it says.** A read rate that fails
  the target is the most valuable output this unit can produce, because it arrives before six other
  units are built on top of it.
