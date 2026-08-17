---
id: 029-mobile-collection-browse
unit: 006-mobile-app
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:22:00Z'
assigned_bolt: 023-mobile-app-shell
implemented: false
---

# Story: 029-mobile-collection-browse

## User Story

**As** a collector standing at a trade table
**I want** to check whether I already own a card
**So that** I do not buy my fourth copy of something — which is the question a phone answers and a
laptop at home does not

## Acceptance Criteria

- [ ] **Given** the app, **When** the collection is browsed, **Then** it uses the **existing**
      collection endpoints with no mobile-specific variant
- [ ] **Given** a search, **When** it runs, **Then** it uses the existing card search, with the same
      ranking the web app gets
- [ ] **Given** a result, **When** it renders, **Then** it shows quantity held, condition and set, and
      the card's approved image where one exists
- [ ] **Given** the collection view, **When** it is used, **Then** there is **no** add, edit, delete or
      bulk action anywhere in it — absent by construction, not disabled
- [ ] **Given** a large collection, **When** it is scrolled, **Then** the list is virtualised and paged
      rather than loaded whole
- [ ] **Given** a filtered view, **When** filters are applied, **Then** they mirror the web app's
      semantics so the same filter means the same thing on both

## Technical Notes

"No mobile-specific variant" is the constraint that keeps this cheap. A bespoke mobile endpoint is a
second API to keep correct, and its divergence from the web one will be discovered by a user rather
than a test.

**Dependency worth stating plainly:** intent 001's bolt 006 — which builds `/collection`, its filters
and the collection table — **has not shipped**. It is listed in the story index as `planned`. If it has
still not shipped when this unit starts, this story is **blocked on it**, and the correct response is
to say so rather than to build a bespoke mobile collection endpoint that would then have to be
reconciled.

## Dependencies

### Requires
- 028-native-pkce-sign-in
- intent 001 / 019-collection-table and 020-collection-filters — **currently `planned`, not built**

### Enables
- 030-mobile-card-detail-and-completion
- 031-offline-collection-cache
- 036-open-card-from-scan

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| `/collection` does not exist yet | This story is blocked and says so. Do not invent a parallel endpoint |
| The collection is empty | Honest empty state pointing at the scanner, which is the app's actual purpose |
| A card has no approved image | Text-only row with the honest empty state, per story 023 |
| The network drops mid-scroll | Falls back to the cached page (story 031) with a visible staleness indicator |

## Out of Scope

- Any editing, ever, on mobile
- Sealed inventory and wishlist — not part of the mobile scope
