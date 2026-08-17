---
id: 025-withdrawal-and-takedown
unit: 005-curation-console
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:14:00Z'
assigned_bolt: 022-curation-console
implemented: false
---

# Story: 025-withdrawal-and-takedown

## User Story

**As** a collector who has changed their mind, or a rights holder who objects
**I want** a way out that actually works
**So that** the permission this product relies on is revocable in practice and not only in the terms

## Acceptance Criteria

- [ ] **Given** a user withdrawing **training** consent, **When** it is processed, **Then** their images
      leave the corpus and are excluded from future dataset versions within the stated window
- [ ] **Given** a user withdrawing **display** consent, **When** it is processed, **Then** any promoted
      image of theirs leaves the projection **synchronously** and the bytes leave storage within the
      stated window
- [ ] **Given** either withdrawal, **When** it completes, **Then** the removal is **verified by a
      test**, not asserted
- [ ] **Given** a rights-holder takedown, **When** it is actioned, **Then** a printing's images can be
      removed **site-wide in one action**
- [ ] **Given** a takedown scoped to a source, a set, or everything, **When** it runs, **Then** seeded
      images matching that scope are purged too (story 010)
- [ ] **Given** a withdrawal, **When** a frozen dataset version referenced the images, **Then** the
      version records the removal without silently altering the metrics it already published
- [ ] **Given** a withdrawn printing, **When** its card page renders, **Then** it returns to the honest
      empty state — it does **not** silently fall back to a seeded image

## Technical Notes

The synchronous requirement on display withdrawal is deliberate and is the one asymmetry in this
story. Training withdrawal can take a window — nothing is publicly visible in the meantime. Display
withdrawal is about something a stranger can currently see, and "within 30 days" is not an acceptable
answer to "take my photograph off your website."

**"Verified by a test" is the criterion that matters most here.** A deletion path that has never been
executed is a promise, and this is the requirement most likely to be exercised by someone who is
already upset. The test must assert the image is gone from the projection, gone from storage, gone
from the corpus and excluded from the next dataset version — four places, because that is how many
places it went.

The seventh criterion closes a loop that would otherwise be a genuine embarrassment: a withdrawn user
image must not cause a *cached publisher image* to reappear in its place. Re-seeding is a decision,
never a fallback.

## Dependencies

### Requires
- 024-consent-capture
- 023-published-image-projection
- 010-seeded-images-bounded

### Enables
- Nothing structurally — this is the story that makes the rest defensible

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| The withdrawn image is the only coverage for a printing | The printing returns to `uncovered`. Correct, and reported |
| A takedown arrives for a printing with dozens of user images | All go. Scope is per printing, not per image |
| A user withdraws and then re-grants | New consent version, new acceptance. Previously deleted images do not return — they are gone |
| Withdrawal races a promotion | Withdrawal wins. The projection refresh on withdrawal is synchronous precisely so this ordering is not ambiguous |
| Storage deletion fails | Retried, and surfaced as an incident rather than logged. A partially-completed deletion is the worst state to be in silently |
| A takedown demands data we no longer have | Respond with what was removed and when. The append-only decision log makes this answerable |

## Out of Scope

- Legal assessment of any particular takedown
- Account deletion generally — that is intent 001's story 035, which must know about captures
