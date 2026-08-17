---
id: 023-published-image-projection
unit: 005-curation-console
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:12:00Z'
assigned_bolt: 022-curation-console
implemented: false
---

# Story: 023-published-image-projection

## User Story

**As** the collection backend
**I want** exactly one read-only table to read for card images
**So that** I can render a picture without being able to reach a single raw capture, prediction or
rejection — the same contract `price_daily` gives me for prices

## Acceptance Criteria

- [ ] **Given** `printing_display_images`, **When** the collection backend reads it, **Then** it is the
      **only** table in `elestrals_scan` it can read, enforced by grant
- [ ] **Given** the projection, **When** it is populated, **Then** it contains **only** approved,
      non-withdrawn images
- [ ] **Given** an unapproved image, **When** any caller requests it by id, **Then** it is **not
      addressable** — the approval gate lives in the projection, not in the UI
- [ ] **Given** a curation decision, **When** it is made, **Then** the projection is refreshed so that
      approval, replacement and withdrawal take effect without a deploy
- [ ] **Given** the projection, **When** it is queried by the collection backend, **Then** the query is
      a **single-table select with explicit columns** — never a join into `scan-api`'s private tables
- [ ] **Given** `scan-api` being down, **When** a card page renders, **Then** the last published
      projection still serves, because it is a table in the database rather than a call to a service

## Technical Notes

A published table, not a view. A view invites a join, and a join is one refactor away from reaching a
column that should never leave `scan-api`. This is exactly the reasoning intent 002 applied to
`price_daily` — *"exposed as a read-only view or a published table, never as a join into the
harvester's private tables"* — and the table form is the stronger of the two options it allowed.

The last criterion is a quiet but valuable property: because the contract is a table rather than an
API call, card images survive `scan-api` being completely down. The collection backend never learns
that the scan service exists.

**Why the gate must be in the projection.** Enforcing "approved only" in the admin UI, or in an API
filter, leaves the underlying object one guessed identifier away from being public. Putting the gate in
what gets published means an unapproved image has no path to a user at all — there is nothing to guess.

## Dependencies

### Requires
- 006-scan-schema-and-grants
- 022-promote-approved-image

### Enables
- Card images on `/cards/:id`, in the mobile card detail (story 030), and in scan candidate lists
  (story 034)

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A withdrawal happens (story 025) | The row leaves the projection within the stated window; the image leaves storage separately, and both are tested |
| The projection refresh fails | Alert, and the previous projection continues to serve. A stale image is a smaller problem than a broken card page — but staleness after a *withdrawal* is not acceptable, so withdrawal refreshes synchronously |
| The collection backend is given a broader grant by accident | Caught by story 006's grant test, which is why that test asserts the negative case |
| A printing's image is requested that has never been approved | Empty state. Not a 404 with a hint that an image exists somewhere |

## Out of Scope

- Deciding what gets approved (story 021)
- The card page rendering itself
