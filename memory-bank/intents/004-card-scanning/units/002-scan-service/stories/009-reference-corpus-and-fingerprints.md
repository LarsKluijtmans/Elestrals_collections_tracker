---
id: 009-reference-corpus-and-fingerprints
unit: 002-scan-service
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T13:44:00Z'
assigned_bolt: 019-scan-service-foundation
implemented: false
---

# Story: 009-reference-corpus-and-fingerprints

## User Story

**As** the server-side matcher
**I want** a fingerprint per printing, each knowing where it came from
**So that** I can compare an incoming frame against the catalog — and so that anyone can ask, at any
moment, how much of the corpus rests on images we photographed versus images we cached

## Acceptance Criteria

- [ ] **Given** a reference image, **When** it is ingested, **Then** a fingerprint row is written with
      its perceptual hash, its embedding, its `printing_id` and its `source`
- [ ] **Given** a fingerprint, **When** its `source` is read, **Then** it is one of `own_photo`,
      `approved_capture` or `seeded` — the provenance is never null and never inferred
- [ ] **Given** the corpus, **When** the index is rebuilt, **Then** it regenerates completely from the
      stored images, so changing the algorithm is a re-index rather than a data migration
- [ ] **Given** an evaluation-role image, **When** the index is built, **Then** it is **excluded**, and
      the build fails rather than warns if one is encountered
- [ ] **Given** a printing with no fingerprint, **When** it is queried, **Then** it reports as
      `uncovered` — a state distinct from "matched nothing"
- [ ] **Given** the corpus, **When** it is counted, **Then** coverage is reportable as printings with a
      fingerprint over printings in the catalog, broken down by `source`

## Technical Notes

Two fingerprints per image, doing different jobs. The perceptual hash is a cheap first cut that
eliminates most of the corpus quickly. The embedding does the ranking.

`index_version` on every row so a re-index is a new version rather than an in-place mutation, and so a
harness run in unit 004 can name the index it measured.

**Do not add a vector index yet.** At 50k fingerprints a linear scan is plausibly inside the 1.2s p95
budget, and ADR-002 already set this project's precedent: it chose a tiered SQL scan over FULLTEXT for
card search because the simpler thing was two orders of magnitude inside budget. Measure first; if the
scan does not hold, that measurement is the justification for the index and belongs in an ADR.

The `source` column is not bookkeeping. FR-16 accepts a legal risk on seeded images on the condition
that it is bounded and shrinking, and a claim that something is shrinking requires being able to count
it.

## Dependencies

### Requires
- 002-photograph-reference-set
- 006-scan-schema-and-grants

### Enables
- 010-seeded-images-bounded
- 014-server-image-match
- 022-promote-approved-image — an approved capture becomes a fingerprint here

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A printing has several reference images | All are fingerprinted; the matcher takes the best distance among them |
| Two printings are visually identical (same art, different edition stamp) | Both fingerprint near-identically. The matcher must return both as candidates rather than picking one — this is exactly the ambiguity story 015's margin exists for |
| An image is corrupt or unreadable at index time | Skipped, counted, and named in the build report. A silent skip makes a coverage number lie |
| The embedding model changes | New `index_version`, full rebuild, and unit 004's harness re-run before anything ships |

## Out of Scope

- The matching itself (story 014)
- Seeded image policy specifics (story 010)
- Displaying any of these images (story 022)
