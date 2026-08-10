---
id: 033-public-collection
unit: 007-profile-and-sharing
intent: 001-collection-tracker
status: ready
priority: could
created: 2026-08-09T12:00:00Z
assigned_bolt: 009-profile-and-sharing
implemented: false
---

# Story: 033-public-collection

## User Story

**As a** collector
**I want** to show my collection to other people
**So that** I can share what I have without exporting a spreadsheet

## Acceptance Criteria

- [ ] **Given** I have not changed anything, **Then** my visibility is `private`
- [ ] **Given** I choose `link`, **Then** an unguessable token is generated and the page is `noindex`
- [ ] **Given** I choose `public`, **Then** it is reachable at `/u/:handle`
- [ ] **Given** the page renders, **Then** the response is built from a **separate whitelist model** containing only printing, condition and quantity
- [ ] **Given** a future field is added to inventory, **Then** it cannot appear here, because the public model never had cost basis, acquisition price or date, storage location or notes
- [ ] **Given** a collection is private, **Then** the URL returns 404 — not 403
- [ ] **Given** the response model is tested, **Then** an assertion proves no cost-basis field exists on the public shape

## Technical Notes

- Whitelist, not filter. Filtering fields out is a rule someone forgets to apply to the next field; a separate model that never had them is a rule that enforces itself.

## Dependencies

### Requires
- 030-profile-settings
- 013-add-inventory-item

### Enables
- Phase 3 seller profile extends this page

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Handle changed while a link is circulating | Old URL 404s; warned at change time |
| Visibility switched to private while someone is viewing | Next request 404s |
| Collection with 10,000 items | Paginated and cached; public traffic must not be able to load the database |

## Out of Scope

- Seller reputation — phase 3
