---
bolt: 009-profile-and-sharing
stage: test
status: partial
created: 2026-08-17T22:10:00Z
---

# Test Report: 009-profile-and-sharing

**Status: `partial`, on one story rather than a criterion.** Story 031 (avatar upload) is not built.
Everything else — the outbox, the public projection, deletion — is complete and tested.

## Automated

```
backend  → pytest -q       542 passed   (was 476; +66)
frontend → tsc --noEmit    clean
frontend → vite build      clean
```

| Module | Coverage |
|---|---|
| `deletion_service.py` | 100% |
| `public_profile_service.py` | 100% |
| `controllers/account.py` | 98% |
| `notification_service.py` | 96% |
| **This bolt's total** | **98%** |

## Three assertions, one per story

**`test_a_failed_delivery_is_retried_not_lost`** — the outbox's whole reason to exist. With the
sender raising, the entry stays `pending`, records the error, backs off, and delivers when a working
sender drains it. This is what intent 002's story 034 was blocked on: "an outage delays rather than
loses" is an acceptance criterion there and there was nothing to delay *in*.

**`test_the_public_shape_has_no_cost_basis_field`** — written against `PublicHolding`'s dataclass
fields rather than against a response, so it fails when somebody *adds* a field, not merely when
somebody happens to have set one. The bolt notes asked to be pedantic about whitelist-not-filter and
this is what that pedantry looks like as a test. A companion at the API level proves the JSON too,
with a row that has a cost basis, a location and a note populated.

**`test_deletion_removes_every_table_keyed_on_the_subject`** — enumerated over `TABLES`, so adding a
user-owned table without adding it there fails here rather than silently leaving rows behind after
an erasure somebody was told was complete.

## The bug the tests caught — for the third time in this project

The outbox drain matched **nothing**, silently. `next_attempt_at` was written as an aware datetime
and compared against another aware datetime, but the column reads back **naive** — `DateTime(timezone=True)`
is a promise neither MySQL nor SQLite keeps.

This project has now hit it three times:

1. Bolt 014 (harvest): *"`computed_at` comes back naive from both MySQL and SQLite whatever
   `DateTime(timezone=True)` suggests, so the staleness comparison raised."*
2. Bolt 009, here.
3. And the same shape lurking in `deletion_requests.execute_after`, fixed at the same time before it
   could bite.

The first occurrence raised a `TypeError`, which is loud. **This one did not.** The `WHERE` clause
simply matched no rows, so every notification sat pending forever with no error anywhere — the
failure mode that would have reached production undetected. A `models/base.utc_naive()` helper now
carries the rule and the history, and anything a `WHERE` clause compares goes through it.

The second fix is smaller and better: `next_attempt_at` is now **NULL on enqueue** rather than "now".
A fresh entry has no backoff, the drain already reads NULL as due, and there is simply nothing to
compare until something has actually failed.

## Deletion, and how an audit survives an erasure

The tables are split on purpose. `deletion_requests` holds a `user_sub` and goes when the deletion
runs. `deletion_audits` outlives it and holds a **SHA-256 of the subject**, plus counts.

That gets story 035's third and fifth criteria at once, which look contradictory: retain only a
non-personal record, *and* let an operator verify a deletion happened. Somebody holding the `sub` can
present it and get a yes; somebody holding only the audit table learns nothing about whose data it
was. `test_the_audit_record_does_not_contain_the_subject` asserts the subject appears nowhere in the
row, and `test_the_audit_is_verifiable_from_the_subject` asserts the other half.

The hash is unsalted, deliberately — a per-record salt would make it unverifiable, which is the whole
purpose. Different threat model from password storage.

## Re-authentication

`X-Reauth-Token` is verified against the same JWKS as the bearer, via a `verify_raw_token` split out
of the FastAPI dependency. Re-implementing the verification for the second token would have been how
the two drift apart, with one of them eventually missing an issuer check.

Three tests: absent token → 401, unverifiable token → 401, and **a valid token for a different
account → 401**. That last one is the interesting one; without it, presenting somebody else's fresh
token would delete this account.

Cancelling deliberately requires no re-authentication. It is the safe direction, and friction in
front of stopping an irreversible action is friction pointing the wrong way.

## Not built

**Story 031 — avatar upload.** It needs storage-api reachable and a browser-to-storage upload with
the *user's own* token rather than the M2M credential, which is the part worth getting right and the
part that cannot be written blind. Every other platform integration in this app is behind the same
gate: `ENABLE_ENRICHMENT`, `ENABLE_PROJECT_LOGGING` and `ENABLE_USAGE_METERING` are all still off
because the M2M service account does not hold the seven scopes (bolt 001's open item).

Also unwired, and for the same reason: **the outbox has no real sender.** The default raises on the
first drain rather than quietly marking things sent, which is the correct failure for a
misconfiguration — but it means the queue currently accumulates rather than delivers. The rows are
written, which is the half that matters; delivery is one function away once notification-api is
reachable.

## Notes

`account` notifications cannot be set to `none`, and the option is not offered rather than offered
and rejected — so nobody discovers the rule by hitting an error. A deletion confirmation is not
marketing.

A `link`-shared collection is deliberately **404 by handle**. Reaching it both ways would make the
token pointless, and the token is the only revocation a shared URL has — which is why rotating it is
a visible button rather than something buried in a form.
