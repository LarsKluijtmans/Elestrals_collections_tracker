---
id: 009-profile-and-sharing
unit: 007-profile-and-sharing
intent: 001-collection-tracker
type: ddd-construction-bolt
status: planned
stories:
  - 030-profile-settings
  - 031-avatar-upload
  - 032-notification-preferences
  - 033-public-collection
  - 035-account-data-deletion
created: 2026-08-09T12:00:00Z
started: null
completed: null
current_stage: null
stages_completed: []

requires_bolts:
  - 004-inventory-core
enables_bolts: []
requires_units: []
blocks: false

complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 1
  testing_scope: 2
---

# Bolt: 009-profile-and-sharing

## Overview

The account surface: app preferences over platform identity, avatars through storage-api,
notification channels with a retrying outbox, optional public sharing, and data deletion.

## Objective

A user understands exactly what this app controls versus what the platform controls, can be reached
in the way they choose, can share their collection safely, and can leave completely.

## Stories Included

- **030-profile-settings**: enriched identity + app preferences (Should)
- **031-avatar-upload**: end-user owned file via storage-api (Should)
- **032-notification-preferences**: channels + outbox (Should)
- **033-public-collection**: `/u/:handle` with a whitelist projection (Could)
- **035-account-data-deletion**: re-authenticated erasure within 30 days (Should)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [ ] **1. model**: Pending → ddd-01-domain-model.md
- [ ] **2. design**: Pending → ddd-02-technical-design.md
- [ ] **3. implement**: Pending → `frontend/src/pages/settings/`, `backend/app/services/profile*`
- [ ] **4. test**: Pending → ddd-03-test-report.md

## Dependencies

### Requires
- 001-platform-foundation (`user_profiles`, M2M enrichment)
- 004-inventory-core (the public view projects over inventory)

### Enables
- Nothing in phase 1. Intent 003 extends `/u/:handle` into a seller profile.

## Success Criteria

- [ ] Email and display name are read-only, with a link to the platform's `/account`
- [ ] Handle uniqueness enforced with a clear conflict message
- [ ] Avatar uploads browser → storage-api with the user's own token; no M2M involved
- [ ] Test notification reaches the chosen channel
- [ ] With notification-api stopped, entries queue and deliver on recovery; dead-letter after 5 attempts
- [ ] `/u/:handle` returns 404 for a private collection
- [ ] **A response-model test asserts the public shape has no cost-basis field**
- [ ] Deletion removes every row keyed on `sub` and retains only a non-personal audit record
- [ ] Coverage > 80%

## Notes

Scheduled last because nothing depends on it, and because a public URL is a promise about a shape —
it should not be made until the inventory model has stopped moving.

The one thing worth being pedantic about: **the public projection is a whitelist model, not a
filtered one.** Filtering fields out is a rule someone forgets to apply to the next field. Building
the response from a separate model that never had cost basis, acquisition price, location or notes
is a rule that enforces itself.
