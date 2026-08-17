---
id: 010-seeded-images-bounded
unit: 002-scan-service
intent: 004-card-scanning
status: ready
priority: should
created: '2026-08-17T13:45:00Z'
assigned_bolt: 019-scan-service-foundation
implemented: false
---

# Story: 010-seeded-images-bounded

## User Story

**As** the person whose name goes on the accepted risk
**I want** cached reference images to be flagged, never displayed, and deleted the moment a
photograph of our own replaces them
**So that** the exposure I accepted is one that shrinks as the product is used, rather than a decision
that quietly becomes permanent

## Acceptance Criteria

- [ ] **Given** a cached reference image, **When** it is stored, **Then** its fingerprint row carries
      `source = 'seeded'` and it is countable at any moment
- [ ] **Given** a seeded image, **When** any user or admin requests an image for that printing,
      **Then** it is **not** returned — seeded images exist to be fingerprinted and are never displayed
      to anyone
- [ ] **Given** a printing with a seeded image, **When** an approved capture for that printing exists,
      **Then** the seeded image is deleted and the fingerprint rebuilt from the approved capture
- [ ] **Given** the corpus, **When** seeded coverage is reported, **Then** it shows the count and its
      trend, so "shrinking" is observable rather than asserted
- [ ] **Given** a purge request, **When** it is scoped to a source, a set, or everything, **Then** it
      removes the matching seeded images and their fingerprints, and the path is **covered by a test**
- [ ] **Given** this story, **When** it is implemented, **Then** an ADR records the accepted risk, its
      named owner and its review triggers, in the form ADR-004 established

## Technical Notes

This is the story that carries a knowing exception to two existing decisions: the data model's "we
store a URL, never bytes, until we have written permission" note, and ADR-001's finding that the
obvious source prohibits reproduction. The ADR must say so plainly rather than describing the
exception as a technical detail — the project's own precedent (ADR-004 on robots.txt) is that a
convention broken silently reads as one nobody knew about.

The bounding is the substance of the story. Without deletion-on-replacement, "seeded" is just a column
and the exposure is permanent. The replacement trigger fires from story 022's promotion path, so the
two are a pair.

**Worth restating, since it changes how much this story matters:** the flywheel makes this
increasingly unnecessary. Every approved capture removes one seeded image. If uptake is good, this
story's data disappears on its own, which is exactly what the ADR should predict and what the trend
report should show.

## Dependencies

### Requires
- 009-reference-corpus-and-fingerprints

### Enables
- 014-server-image-match — coverage beyond the pilot set depends on it
- 022-promote-approved-image — which triggers the replacement

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| An approved capture is later withdrawn under story 025 | The printing returns to uncovered. It does **not** silently re-seed — re-seeding is a decision, not a fallback |
| A seeded image is the only coverage for a high-value printing | Still never displayed. The matcher works; the card page shows the honest empty state |
| Someone asks for the seeded image for debugging | Refused. "Admin included" is in the acceptance criteria because this is the request that will actually be made |
| A takedown arrives naming a source | The scoped purge is the response, which is why it is tested rather than assumed |

## Out of Scope

- Acquiring the images. This story defines how they are held, flagged and removed, not where they come
  from — that is the ADR's subject
- Public display of anything (story 022)
