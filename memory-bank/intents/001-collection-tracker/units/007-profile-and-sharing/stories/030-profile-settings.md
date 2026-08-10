---
id: 030-profile-settings
unit: 007-profile-and-sharing
intent: 001-collection-tracker
status: ready
priority: should
created: 2026-08-09T12:00:00Z
assigned_bolt: 009-profile-and-sharing
implemented: false
---

# Story: 030-profile-settings

## User Story

**As a** collector
**I want** one place for my account and my app preferences
**So that** I know what this app controls and what the platform controls

## Acceptance Criteria

- [ ] **Given** I open settings, **Then** email and display name show, enriched from auth-api, and are **read-only** with a link to the platform's `/account`
- [ ] **Given** I edit preferences, **Then** handle, collection visibility, default currency and condition scale persist
- [ ] **Given** I claim a taken handle, **Then** I get a clear conflict message
- [ ] **Given** auth-api is unavailable, **Then** the page renders with token claims only and says so
- [ ] **Given** I change the condition scale, **Then** the vocabulary changes everywhere without migrating any data

## Technical Notes

- We never write email, display name or avatar into our tables. They are enriched on read and cached in memory only — one less place for personal data to go stale or leak.

## Dependencies

### Requires
- 001-sign-in-with-platform

### Enables
- 031-avatar-upload
- 033-public-collection
- Phase 3 seller identity

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Handle with reserved words or profanity | Blocklist, with a clear message |
| Handle changed after being shared | Old URL 404s; the user is warned before confirming |
| Enrichment slow | Page renders immediately; identity fields fill in |

## Out of Scope

- Editing anything the platform owns
