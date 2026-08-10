---
id: 010-card-search
unit: 002-card-catalog
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 003-card-catalog-surface
implemented: false
---

# Story: 010-card-search

## User Story

**As a** collector
**I want** to find a card by typing part of its name
**So that** I can add it without knowing its set or number

## Acceptance Criteria

- [ ] **Given** I type three characters, **When** results return, **Then** they arrive in under 150ms p95
- [ ] **Given** results render, **Then** each shows name, set code, collector number, element and rarity
- [ ] **Given** multiple cards match, **Then** exact-name matches rank above prefix matches, which rank above substring matches
- [ ] **Given** results are showing, **When** I press arrow keys, **Then** the highlight moves; `Enter` selects
- [ ] **Given** I am signed out, **When** I search, **Then** it works

## Technical Notes

- **This story's API is the contract the fast-add flow consumes.** Design it as an API for that flow, not only as a page, or it needs reworking two bolts later.
- Cancel in-flight searches on a new keystroke, so a slow earlier response cannot overwrite a newer result set.

## Dependencies

### Requires
- 008-catalog-importer

### Enables
- 012-card-detail
- 016-fast-add-flow

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Fewer than 3 characters | No query fired; the UI stays calm |
| No matches | An empty state, not an error |
| Query with punctuation or diacritics | Normalised before matching |
| 40-character paste | Handled; no results is a calm empty state |

## Out of Scope

- Adding anything — 013
