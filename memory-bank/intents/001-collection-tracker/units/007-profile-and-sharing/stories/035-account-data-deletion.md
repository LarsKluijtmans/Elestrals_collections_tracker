---
id: 035-account-data-deletion
unit: 007-profile-and-sharing
intent: 001-collection-tracker
status: ready
priority: should
created: 2026-08-09T12:00:00Z
assigned_bolt: 009-profile-and-sharing
implemented: false
---

# Story: 035-account-data-deletion

## User Story

**As a** collector leaving the product
**I want** everything this app holds about me removed
**So that** I am not depending on trust alone

## Acceptance Criteria

- [ ] **Given** I request deletion, **Then** I must re-authenticate first
- [ ] **Given** a request is confirmed, **Then** every row keyed on my `sub` is removed within 30 days
- [ ] **Given** deletion completes, **Then** only a non-personal audit record that a deletion occurred is retained
- [ ] **Given** I read the page, **Then** it states plainly that closing the platform account itself happens in the platform's `/account`, and links there
- [ ] **Given** an operator needs assurance, **Then** deletion is verifiable without exposing what was deleted
- [ ] **Given** I change my mind, **Then** a pending request can be cancelled before it executes

## Technical Notes

- Our GDPR surface is small on purpose: we hold a `sub` and app preferences. Identity lives in the platform, so deleting here is genuinely tractable.

## Dependencies

### Requires
- 030-profile-settings

### Enables
- A defensible privacy position at launch

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Deletion requested with an active phase-3 order | Blocked until the order reaches a terminal state, with the reason given |
| User signs in during the 30-day window | Offered the chance to cancel |
| Deletion job fails midway | Idempotent and resumable; the request stays open until fully complete |

## Out of Scope

- Closing the platform account — the platform owns that
