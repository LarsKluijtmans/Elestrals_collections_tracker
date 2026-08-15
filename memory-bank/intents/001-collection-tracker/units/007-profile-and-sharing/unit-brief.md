---
unit: 007-profile-and-sharing
intent: 001-collection-tracker
phase: inception
status: stories-defined
created: '2026-08-09T12:00:00Z'
updated: '2026-08-09T12:00:00Z'
---

# Unit Brief: profile-and-sharing

## Purpose

The account surface: app-owned preferences layered over platform-owned identity, notification
channel preferences with a reliable outbox, optional public sharing of a collection, and the
data-deletion path that makes the privacy promise real.

## Scope

### In Scope
- `/settings/profile` — enriched identity (read-only) plus editable app preferences
- Avatar upload through storage-api as an end-user `owned` file
- `/settings/notifications` — per-event channel preferences
- `notification_outbox` and its retrying worker
- `/u/:handle` — public collection view with a strict projection
- Account data deletion with re-authentication and a 30-day guarantee

### Out of Scope
- Editing email, display name, password, MFA or sessions — all of that lives in the platform's own
  `/account` area and we link to it rather than reimplementing it
- Notification *templates* — notification-api owns those
- Seller profiles and reputation (intent 003 extends `/u/:handle`)

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-14 | Profile and preferences | Should |
| FR-15 | Notification preferences | Should |
| FR-16 | Public collection sharing | Could |
| FR-18 | Account data deletion | Should |

---

## Domain Concepts

### Key Entities
| Entity | Description | Attributes |
|--------|-------------|------------|
| UserProfile | App-owned preferences | `handle`, `collection_visibility`, `default_currency`, `condition_scale` |
| NotificationPreference | Channel choice per event type | `user_sub`, `event_type`, `channels` |
| OutboxEntry | A queued notification | `channel`, `template_key`, `context`, `state`, `attempts` |
| DeletionRequest | A pending erasure | `user_sub`, `requested_at`, `execute_after`, `state` |
| PublicCollectionView | The safe projection | printing, condition, quantity — **and nothing else** |

### Key Operations
| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `get_profile` | Merge platform identity with app preferences | `sub` | profile |
| `set_handle` | Claim a unique public handle | `sub`, handle | profile or conflict |
| `enqueue_notification` | Queue, then deliver best-effort | user, template, context | outbox entry |
| `drain_outbox` | Retry with backoff | — | delivery results |
| `render_public_collection` | Safe projection by handle | handle, viewer | items or 404 |
| `request_deletion` | Start erasure after re-auth | `sub` | deletion request |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 5 |
| Must Have | 0 |
| Should Have | 4 |
| Could Have | 1 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 030-profile-settings | Profile and preferences | Should | Planned |
| 031-avatar-upload | Upload an avatar | Should | Planned |
| 032-notification-preferences | Choose notification channels | Should | Planned |
| 033-public-collection | Share my collection publicly | Could | Planned |
| 035-account-data-deletion | Delete my data | Should | Planned |

---

## Dependencies

### Depends On
| Unit | Reason |
|------|--------|
| 001-platform-foundation | `user_profiles`, M2M client, enrichment |
| 003-inventory-core | The public view projects over inventory |

### Depended By
| Unit | Reason |
|------|--------|
| — | Leaf in phase 1. Intent 003 extends `/u/:handle` into a seller profile |

### External Dependencies
| System | Purpose | Risk |
|--------|---------|------|
| auth-api | identity enrichment | Low — degrade to token claims |
| storage-api | avatar bytes | Low — disable upload, keep the page |
| notification-api | delivery | Low — outbox retries |

---

## Technical Context

### Suggested Technology
Avatar upload uses `react-auth`'s `useStorage` hook directly from the browser with the user's own
token — storage-api forces the file to `owned` and scopes it to the caller's `sub`, so no M2M
credential is involved and the backend never touches the bytes.

The outbox worker runs on the same scheduler as the catalog importer in phase 1, with exponential
backoff and a dead-letter state after 5 attempts.

### Integration Points
| Integration | Type | Protocol |
|-------------|------|----------|
| auth-api | API | M2M `users.get` |
| storage-api | API | end-user token, `owned` files |
| notification-api | API | M2M `notifications.send` |

### Data Storage
| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| `notification_preferences` | SQL | per user per event type | life of account |
| `notification_outbox` | SQL | transient | 30 days after terminal state |
| `deletion_requests` | SQL | rare | audit row retained without personal data |

---

## Constraints

- **The public projection is a whitelist, not a filter.** It is built from an explicit list of safe
  fields — printing, condition, quantity. Cost basis, acquisition price, acquisition date, storage
  location and notes are structurally absent from the response model, so a future field addition
  cannot leak them by default.
- Default visibility is `private`. `link` uses an unguessable token, and a link view is
  `noindex`.
- Deletion requires re-authentication. It removes every row keyed on the user's `sub` and retains
  only a non-personal audit record that a deletion occurred.
- We never write email, display name or avatar into our tables. They are read from auth-api on
  demand and cached in memory only.
- The platform account itself is closed in the platform's `/account`; this page links there and
  says so plainly.

---

## Success Criteria

### Functional
- [ ] Profile shows platform-owned fields as read-only with a link to the platform account area
- [ ] Handle uniqueness is enforced, with a clear conflict message
- [ ] Avatar uploads, displays, and is deletable by its owner and nobody else
- [ ] A test notification reaches the selected channel
- [ ] With notification-api stopped, the entry queues and delivers on recovery
- [ ] `/u/:handle` returns 404 for a private collection and never includes a price the owner paid
- [ ] A deletion request removes all app-owned rows and is verifiable

### Non-Functional
- [ ] Profile page p95 < 300ms including enrichment
- [ ] Outbox drains within 5 minutes of notification-api recovering
- [ ] A response-model test asserts the public projection contains no cost-basis field

### Quality
- [ ] Code coverage > 80%
- [ ] Code reviewed and approved

---

## Bolt Suggestions

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| 009-profile-and-sharing | DDD | 030, 031, 032, 033, 035 | Preferences, avatar, notification outbox, public projection, deletion |

---

## Notes

Scheduled last on purpose. Nothing depends on it, and public sharing in particular should not exist
until the inventory model has stopped moving — a public URL is a promise about a shape, and shapes
in flight break links.

The whitelist projection is the one thing in this unit worth being pedantic about. Filtering fields
out is a rule someone forgets to apply to the next field; building the response from a separate
model that never had those fields is a rule that enforces itself.
