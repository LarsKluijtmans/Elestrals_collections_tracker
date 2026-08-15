---
id: 031-avatar-upload
unit: 007-profile-and-sharing
intent: 001-collection-tracker
status: ready
priority: should
created: 2026-08-09T12:00:00Z
assigned_bolt: 009-profile-and-sharing
implemented: false
---

# Story: 031-avatar-upload

## User Story

**As a** collector
**I want** a picture on my profile
**So that** I am recognisable when the marketplace arrives

## Acceptance Criteria

- [ ] **Given** I pick a file, **Then** it uploads browser → storage-api directly, carried by my own access token
- [ ] **Given** the upload lands, **Then** storage-api has forced it to an `owned` file scoped to my `sub`, with no M2M credential involved
- [ ] **Given** I own an avatar, **Then** I can replace and delete it, and nobody else can
- [ ] **Given** the file is too large or my quota is exhausted, **Then** I get a clear inline message naming the limit
- [ ] **Given** storage-api is unavailable, **Then** upload is disabled and the rest of the page still works

## Technical Notes

- Uses `react-auth`'s `useStorage` hook. The backend never touches the bytes, which is why no M2M secret is involved in a user uploading their own picture.

## Dependencies

### Requires
- 030-profile-settings

### Enables
- Phase 3 listing photos use the same path

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Non-image file | Rejected client-side and server-side |
| Very large image | Downscaled client-side before upload |
| Upload interrupted | No partial file; the previous avatar remains |

## Out of Scope

- Listing photos — phase 3
