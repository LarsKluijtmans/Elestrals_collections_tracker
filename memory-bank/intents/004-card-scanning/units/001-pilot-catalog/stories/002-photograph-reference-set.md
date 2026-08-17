---
id: 002-photograph-reference-set
unit: 001-pilot-catalog
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T13:36:00Z'
assigned_bolt: 018-pilot-catalog
implemented: false
---

# Story: 002-photograph-reference-set

## User Story

**As** the matcher
**I want** a photograph of every printing in the pilot set, each bound to its `printing_id` at the
moment it was taken
**So that** I have something to compare an incoming frame against — and so that every label I am later
measured on is a fact rather than someone's recollection

## Acceptance Criteria

- [ ] **Given** the compiled pilot set, **When** photography completes, **Then** every printing has at
      least one reference photograph
- [ ] **Given** a photograph, **When** it is taken, **Then** its `printing_id` is recorded in the
      manifest **at capture time** — never inferred afterwards from filename, order or memory
- [ ] **Given** the manifest, **When** it is validated, **Then** every entry resolves to an existing
      printing and every printing resolves to at least one entry, with both directions checked
- [ ] **Given** the photographs, **When** their conditions are reviewed, **Then** they were taken
      handheld under ordinary indoor light — not in a lightbox, not on a scanner
- [ ] **Given** a photograph, **When** it is stored, **Then** it is cropped to the card and carries no
      EXIF GPS, matching what the product will later do on a user's device
- [ ] **Given** the corpus, **When** its role is checked, **Then** every image is marked
      `role = reference` and is eligible for indexing

## Technical Notes

The capture harness must make the label the *first* thing entered and the photograph the second —
select the printing, then shoot. Any workflow that photographs first and labels later will produce
mislabelled rows at a rate proportional to how tired the person is, and mislabelled reference data is
the most expensive kind of error in this intent: it corrupts both what the matcher compares against
and what the harness scores.

Realistic conditions are a requirement, not a shortcut. A lightbox corpus measured against lightbox
evaluation images yields an accuracy figure that does not survive a kitchen table, and the number is
worse than useless because it is believed.

Storage location (repo LFS versus object storage) is decided in this story; the volume is ~150 images
for the pilot but the same pipeline later carries hundreds of thousands.

## Dependencies

### Requires
- 001-compile-pilot-set

### Enables
- 003-held-out-evaluation-set
- 004-ocr-feasibility-spike
- 009-reference-corpus-and-fingerprints
- 017-dataset-versioning — this is dataset version 1

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A printing is not physically owned | Recorded as uncovered in the manifest. Unit 003 must report it as `uncovered`, not as a match failure — the distinction exists because of exactly this case |
| A card is damaged or heavily played | Photograph it anyway and mark the condition. A corpus of only mint cards measures a population that does not exist |
| Foil glare obscures the art | Take a second frame at a different angle; both are reference images for the same printing |
| The same physical card is photographed twice by mistake | Detectable by near-identical fingerprints; deduplicate before story 018's split, or the split leaks |

## Out of Scope

- Evaluation images (story 003) — deliberately a separate shoot
- Fingerprinting (story 009)
- Publishing any of these images to users (story 022)
