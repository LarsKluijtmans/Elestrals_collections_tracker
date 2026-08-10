---
id: 032-notification-preferences
unit: 007-profile-and-sharing
intent: 001-collection-tracker
status: ready
priority: should
created: 2026-08-09T12:00:00Z
assigned_bolt: 009-profile-and-sharing
implemented: false
---

# Story: 032-notification-preferences

## User Story

**As a** collector
**I want** to choose how I am contacted
**So that** the product does not become noise

## Acceptance Criteria

- [ ] **Given** I open notification settings, **Then** I can choose email, in-app inbox, push or none per event type
- [ ] **Given** I send a test, **Then** it reaches the selected channel
- [ ] **Given** a notification is triggered, **Then** it enters `notification_outbox` before any delivery attempt
- [ ] **Given** notification-api is stopped, **Then** entries queue and deliver on recovery — nothing is lost silently
- [ ] **Given** an entry fails 5 times, **Then** it is dead-lettered and visible to an operator
- [ ] **Given** I am a new user, **Then** defaults are conservative: nothing but account-critical mail until I opt in

## Technical Notes

- Outbox-first is what turns a notification-api outage into a delay rather than a loss. Exponential backoff, dead-letter after 5.

## Dependencies

### Requires
- 001-sign-in-with-platform

### Enables
- Phase 2 price alerts use this outbox

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| User has no email on the platform account | Email channel disabled with an explanation |
| Push not registered on any device | Push option shown as unavailable, not silently ignored |
| Outbox grows during a long outage | Bounded; oldest non-critical entries shed with a log |

## Out of Scope

- Notification templates — notification-api owns those
