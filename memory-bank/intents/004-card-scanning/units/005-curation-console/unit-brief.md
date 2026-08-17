---
unit: 005-curation-console
intent: 004-card-scanning
phase: inception
status: stories-defined
created: '2026-08-17T13:20:00Z'
updated: '2026-08-17T13:20:00Z'
---

# Unit Brief: curation-console

## Purpose

The admin half of the flywheel, and the unit where a pile of collectors' photographs becomes an asset.

Three things happen here. An admin **judges** captures — approve, reject with a reason, or relabel to
the printing the model got wrong. Approved captures are **promoted** to the images the site displays,
which is how a catalog that has never held a single image finally gets one. And the **consent,
withdrawal and takedown** machinery exists, because displaying a user's photograph of someone else's
copyrighted artwork is a deliberate act that needs to be revocable.

The judgement is the valuable part. A relabel — the model said Vipyro, the admin says it is the
alt-art printing — is the highest-value row in the entire system: it is a labelled example of exactly
the case the recogniser gets wrong. The queue is ordered to surface those first.

## Scope

### In Scope
- `/admin/scan` curation queue behind `elestrals:admin`, ordered by review value rather than arrival
- `approve` / `reject` with a closed reason / `relabel`, written append-only, submitter withheld
- Promotion of one approved image per printing to display, on an immutable storage-api key
- `printing_display_images` — the read-only projection the collection backend reads, with the
  approval gate enforced *in the projection*
- Versioned consent, separately withdrawable for training and for display
- Withdrawal and rights-holder takedown, both tested
- Grouped, counted rejection reasons

### Out of Scope
- Curating anything other than scan captures — this is not a general moderation system
- The `/cards/:id` rendering of an approved image; the collection backend reads the projection and
  renders it with its existing card-detail code
- Editing the catalog. A relabel points a capture at a different printing; it never edits the printing
- Automatic approval of any kind, at any confidence. A technically correct match can still be an
  unusable photograph

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-13 | Admin curation queue | Must |
| FR-14 | Approved captures become the catalog's displayed images | Must |
| FR-17 | Consent, moderation and takedown for submitted images | Must |

---

## Domain Concepts

### Key Entities

| Entity | Description | Attributes |
|--------|-------------|------------|
| CurationQueueItem | A capture awaiting judgement, with its review-value score | `capture_id`, `predicted_printing_id`, `top_confidence`, `user_confirmed_printing_id`, `review_value`, `queued_at` |
| CurationDecision | The judgement, append-only | `capture_id`, `decision`, `reason`, `relabelled_printing_id`, `decided_by`, `decided_at` |
| PrintingDisplayImage | The published contract row | `printing_id`, `object_key`, `approved_by`, `approved_at`, `contributor_credit`, `withdrawn_at` |
| ConsentRecord | What a user agreed to, and when | `user_sub`, `consent_version`, `training`, `display`, `accepted_at`, `withdrawn_at` |
| TakedownRequest | A rights-holder demand | `scope`, `printing_id`, `requested_by`, `actioned_at` |

### Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `queue(order)` | List captures worth reviewing first | filters | queue page |
| `decide(capture, decision, reason)` | Judge one capture | capture, decision | decision row |
| `promote(capture)` | Make an approved image the display image | capture | display image row |
| `publish()` | Refresh the read-only projection | — | projection rows |
| `withdraw(user, aspect)` | Remove from training, display, or both | user, aspect | count removed |
| `takedown(scope)` | Remove a printing's images site-wide | scope | count removed |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 6 |
| Must Have | 5 |
| Should Have | 1 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 021-curation-queue | Judge the captures that are worth judging first | Must | Planned |
| 022-promote-approved-image | The catalog gets its first images | Must | Planned |
| 023-published-image-projection | One read-only contract, and no way around it | Must | Planned |
| 024-consent-capture | Say what will happen to the photograph, before it is taken | Must | Planned |
| 025-withdrawal-and-takedown | A way out, tested rather than promised | Must | Planned |
| 026-rejection-analytics | What the recogniser is systematically getting wrong | Should | Planned |

---

## Dependencies

### Depends On

| Unit | Reason |
|------|--------|
| 002-scan-service | Captures to curate, and the schema they live in |
| 004-evaluation-and-dataset | Queue ordering uses confidence bands; before calibration they are arbitrary numbers |
| intent 002 / 005-admin-console | The `elestrals:admin` dependency, the admin SPA section and its code-splitting are reused, not rebuilt |

### Depended By

| Unit | Reason |
|------|--------|
| 007-scan-experience | Not blocking — candidate lists render an honest empty state until images exist, and look considerably better afterwards |

### External Dependencies

| System | Purpose | Risk |
|--------|---------|------|
| storage-api | approved image bytes on immutable keys | Low |
| `elestrals:admin` scope | the gate on everything in this unit | **Resolved** — confirmed available 2026-08-17 |

---

## Technical Context

### Suggested Technology

The API lives in `scan-api`; the UI is a code-split section of the existing SPA's admin area, so a
non-admin never downloads it — the pattern intent 002 established for `/admin/harvest`. The projection
is a published table refreshed on decision, not a view with a join, so the collection backend's read
path stays a single-table select and cannot accidentally reach a private column.

Review-value ordering is a computed score, not a sort key the admin picks: uncovered printings first,
then user corrections, then low-confidence accepts, then everything else.

### Integration Points

| Integration | Type | Protocol |
|-------------|------|----------|
| `scan_captures` / `scan_predictions` | inbound read | SQLAlchemy within `scan-api` |
| `printing_display_images` | outbound publish | MySQL, read-only grant for the collection backend |
| storage-api | outbound | HTTPS, M2M |
| SPA admin section | inbound | HTTPS, `elestrals:admin` |

### Data Storage

| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| `curation_decisions` | SQL | ~2M | permanent |
| `printing_display_images` | SQL | 50k max, one per printing | permanent, withdrawable |
| `consent_records` | SQL | one per user per version | permanent — a withdrawal must be provable |

---

## Constraints

- **No automatic promotion, at any confidence.** A correct match can still be a blurry photograph of a
  card under a lamp.
- **The approval gate lives in the projection.** Enforcing it only in the UI means an unapproved image
  is one guessed id away from being public.
- **The queue never shows the submitter.** A curator judging a card does not need to know whose shoebox
  it came from, and giving them information they cannot use is how it gets used.
- **Rejection deletes the image.** "Unapproved but retained just in case" is how a store of rejected
  photographs accumulates with nobody deciding to keep it.
- **Consent for training and consent for display are separate, and separately withdrawable.** They are
  materially different asks and bundling them makes both meaningless.
- **Withdrawal is tested.** A deletion path that has never been executed is a promise, and this is the
  requirement most likely to be relied upon by someone who is upset.
