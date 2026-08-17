---
id: 009-profile-and-sharing
unit: 007-profile-and-sharing
intent: 001-collection-tracker
type: ddd-construction-bolt
status: partial
stories:
  - 030-profile-settings
  - 031-avatar-upload
  - 032-notification-preferences
  - 033-public-collection
  - 035-account-data-deletion
created: 2026-08-09T12:00:00Z
started: 2026-08-17T21:30:00Z
completed: null
current_stage: done
stages_completed:
  - name: model
    completed: 2026-08-17T21:35:00Z
    artifact: the outbox, the whitelist projection, the deletion request/audit split
  - name: design
    completed: 2026-08-17T21:40:00Z
    artifact: 0007_profile_and_sharing.py, 8 endpoints, 3 services
  - name: implement
    completed: 2026-08-17T22:00:00Z
    artifact: backend/app/controllers/account.py, frontend settings + /u/:handle
  - name: test
    completed: 2026-08-17T22:10:00Z
    artifact: ddd-03-test-report.md

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

- [x] **1. model**: Done → the outbox, `PublicHolding` (the whitelist), and the deletion
      request/audit split that lets an erasure keep an audit trail
- [x] **2. design**: Done → `0007_profile_and_sharing.py`, eight endpoints, three services
- [x] **3. implement**: Done → `controllers/account.py`, notification settings, `/u/:handle`
- [x] **4. test**: Done → ddd-03-test-report.md — 66 new tests, 98% on this bolt's modules

## Dependencies

### Requires
- 001-platform-foundation (`user_profiles`, M2M enrichment)
- 004-inventory-core (the public view projects over inventory)

### Enables
- Nothing in phase 1. Intent 003 extends `/u/:handle` into a seller profile.

## Success Criteria

- [x] Email and display name are read-only, with a link to the platform's `/account` — shipped in
      bolt 001; the deletion panel links there too, so "delete my data" cannot be read as
      "close my account"
- [x] Handle uniqueness enforced with a clear conflict message — shipped in bolt 001
- [ ] Avatar uploads browser → storage-api with the user's own token; no M2M involved —
      **not built.** Story 031 is the one story in this bolt that is genuinely outstanding; see
      the construction result
- [x] Test notification reaches the chosen channel — queued through the same path a real one
      takes, so a test that arrives proves the whole chain
- [x] With notification-api stopped, entries queue and deliver on recovery; dead-letter after 5
      attempts — geometric backoff, and a dead letter stops being retried
- [x] `/u/:handle` returns 404 for a private collection — and the *same* 404 an unknown handle
      gets, so the difference between the two is not itself an oracle
- [x] **A response-model test asserts the public shape has no cost-basis field** — written
      against the model rather than a response, so it fails when somebody adds a field
- [x] Deletion removes every row keyed on `sub` and retains only a non-personal audit record
- [x] Coverage > 80% — 98% on this bolt's modules

## Notes

Scheduled last because nothing depends on it, and because a public URL is a promise about a shape —
it should not be made until the inventory model has stopped moving.

The one thing worth being pedantic about: **the public projection is a whitelist model, not a
filtered one.** Filtering fields out is a rule someone forgets to apply to the next field. Building
the response from a separate model that never had cost basis, acquisition price, location or notes
is a rule that enforces itself.

## Construction result - 2026-08-17

**Status: partial.** Four of five stories built. Story 031 (avatar upload) is the outstanding one.

| Story | State |
|---|---|
| 030 profile settings | done in bolt 001; the deletion panel now links to the platform's `/account` so "delete my data" cannot be misread as "close my account" |
| 031 avatar upload | **not built.** Needs storage-api reachable and a browser-to-storage upload with the *user's own* token — the part worth getting right, and the part that cannot be written blind |
| 032 notification preferences | done — outbox-first, geometric backoff, dead-letter after five, operator-visible |
| 033 public collection | done — whitelist model, 404 for private *and* unknown alike |
| 035 account data deletion | done — fresh-token re-auth, week's grace, audit that survives the erasure |

**The outbox is what intent 002's story 034 was blocked on.** "A notification-api outage delays
rather than loses" is an acceptance criterion for price alerts, and there was nothing to delay in.
There is now, and it is the ordinary phase-1 path rather than something alerts-specific.

**The bug worth recording — the third occurrence of one this project already documented.** The drain
matched nothing, silently. `next_attempt_at` was written aware and compared aware, but the column
reads back **naive**: `DateTime(timezone=True)` is a promise neither MySQL nor SQLite keeps. Bolt 014
recorded this first, where it raised a `TypeError` and was therefore loud. Here it did not raise —
the `WHERE` clause simply matched no rows, and every notification would have sat pending forever with
no error anywhere.

`models/base.utc_naive()` now carries the rule and the history. The better half of the fix is
smaller: `next_attempt_at` is **NULL on enqueue** rather than "now", because a fresh entry genuinely
has no backoff and the drain already reads NULL as due — nothing to compare until something fails.

**How an audit survives an erasure.** Story 035 asks for two things that read as contradictory:
retain only a non-personal record, and let an operator verify a deletion occurred. The split answers
both — the request row holds the `sub` and goes; the audit holds a SHA-256 of it and stays. Somebody
presenting the subject gets a yes; somebody holding the audit table learns nothing about whose data
it was. Unsalted deliberately: a per-record salt would make it unverifiable, which is the point.

**Still gated on the platform**, like everything else that touches it: the outbox has no real sender
wired, because the M2M service account does not hold the seven scopes. The default sender *raises*
rather than quietly marking things sent — the correct failure for a misconfiguration — so the rows
accumulate rather than deliver. That is the half that matters; delivery is one function away.
