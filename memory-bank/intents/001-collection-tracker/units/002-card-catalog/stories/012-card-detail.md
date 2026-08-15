---
id: 012-card-detail
unit: 002-card-catalog
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 003-card-catalog-surface
implemented: false
---

# Story: 012-card-detail

## User Story

**As a** collector
**I want** one page per card showing every way it was printed
**So that** I can record the exact version I own

## Acceptance Criteria

- [ ] **Given** I open a card, **Then** I see art, name, type, element, rune type, stats, spirit cost, rules text and artist
- [ ] **Given** the page renders, **Then** a table lists every printing: rarity, finish, language, edition
- [ ] **Given** I am signed in, **Then** my owned quantity per printing shows inline
- [ ] **Given** the page renders, **Then** rarity is a material treatment and element is a named tinted chip
- [ ] **Given** an image renders, **Then** its alt text is `"{name} — {set} {rarity}"`
- [ ] **Given** I am signed out, **Then** the page works

## Technical Notes

- This page is the link target for search results, collection rows, set checklists, and later listings — so its URL shape should not change after phase 1.
- The price tab is added in intent 002; leave the tab structure in place but do not stub a zero.

## Dependencies

### Requires
- 008-catalog-importer

### Enables
- Phase 2 price tab
- Phase 3 listings tab

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Image URL 404s | Placeholder with the card name; never a broken-image icon |
| Card with no rules text | Section omitted, not rendered empty |
| Card printed in multiple sets | Each set is its own card page; cross-links between them |

## Out of Scope

- Prices — intent 002
