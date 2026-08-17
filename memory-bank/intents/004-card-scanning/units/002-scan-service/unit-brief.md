---
unit: 002-scan-service
intent: 004-card-scanning
phase: inception
status: draft
created: '2026-08-17T13:05:00Z'
updated: '2026-08-17T13:05:00Z'
---

# Unit Brief: scan-service

## Purpose

Stand up the third backend. Everything in this intent that stores an image, holds a fingerprint, or
answers an identification request runs inside **`scan-api`** — a separately deployable FastAPI service
owning the `elestrals_scan` schema, with its own Alembic tree and its own MySQL user.

This unit builds the service, the schema, the grants that make the isolation real, the append-only
capture store, and the reference corpus the matcher will read.

The isolation has a different justification from `harvest-api`'s. A blocked scraper costs coverage
tomorrow; a slow matcher costs a person standing in a card shop holding a card. `scan-api` is on the
user's request path and `harvest-api` never is, so this service is isolated for **latency** as much as
for availability — and the degradation mode is specific: unreachable means the ladder falls back to
the device, says so, and the add still completes.

## Scope

### In Scope
- `scan-api` service skeleton: FastAPI app, config, `/health`, container, compose and release wiring
- `elestrals_scan` schema with its own Alembic tree
- A third MySQL user, with no write grant on `elestrals` or `elestrals_harvest`, and the read grants
  it genuinely needs
- `scan_captures`, `scan_predictions`, `curation_decisions` — append-only by design and by test
- The capture upload endpoint: validation, server-side verification of what the client promised,
  re-encode at a bounded resolution
- `printing_fingerprints` with provenance, and the index build/rebuild path
- The seeded-image policy: flagged, never displayed, deleted on replacement, purgeable

### Out of Scope
- The ladder, the matching algorithm and the calibration (unit 003) — this unit ships the frame and
  the storage, not the recogniser
- The curation queue and any admin UI (unit 005) — this unit's surface is the API and the CLI
- Dataset versioning and the harness (unit 004)
- Anything in the `elestrals` schema. This service cannot write it, by grant

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-22 | The matcher is a third backend | Must |
| FR-11 | The capture store — every scan retained with prediction and outcome | Must |
| FR-16 | Seeded reference images — accepted risk, bounded and shrinking | Should |

---

## Domain Concepts

### Key Entities

| Entity | Description | Attributes |
|--------|-------------|------------|
| ScanCapture | One image a user submitted, cropped and stripped | `id`, `user_sub`, `object_key`, `width`, `height`, `bytes`, `created_at`, `consent_version` |
| ScanPrediction | What the system claimed for a capture, as shown to the user | `capture_id`, `pass_no`, `engine`, `candidates JSON`, `top_confidence`, `outcome`, `failure_reason` |
| CurationDecision | An admin's judgement about a capture | `capture_id`, `decision`, `reason`, `relabelled_printing_id`, `decided_by`, `decided_at` |
| PrintingFingerprint | What the matcher compares against | `printing_id`, `phash`, `embedding`, `source`, `image_object_key`, `built_at`, `index_version` |
| SeededImage | A cached reference image, never shown, awaiting replacement | fingerprint row with `source = 'seeded'` |

### Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `upload(frame, user_sub)` | Validate, verify, re-encode, store | image bytes | capture id |
| `record_prediction(capture, pass, candidates)` | Write what was shown, once | capture, pass result | prediction id |
| `fingerprint(image, printing)` | Derive phash + embedding | image, printing id | fingerprint row |
| `rebuild_index(version)` | Regenerate the whole index from stored images | index version | count, duration |
| `replace_seeded(printing)` | Delete the seeded image, rebuild from the approved capture | printing id | fingerprint row |
| `purge_seeded(scope)` | Remove seeded images per source, per set, or wholesale | scope | count purged |

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
| 005-scan-api-skeleton | A third deployable backend | Must | Planned |
| 006-scan-schema-and-grants | Own schema, own user, no write grant on `elestrals` | Must | Planned |
| 007-capture-store | Every scan retained, append-only, owner-scoped | Must | Planned |
| 008-capture-upload-endpoint | An upload endpoint that trusts nothing the client says | Must | Planned |
| 009-reference-corpus-and-fingerprints | Fingerprints with provenance, and a rebuildable index | Must | Planned |
| 010-seeded-images-bounded | An accepted risk that shrinks instead of accumulating | Should | Planned |

---

## Dependencies

### Depends On

| Unit | Reason |
|------|--------|
| 001-pilot-catalog | Something to fingerprint |
| intent 001 / 001-platform-foundation | Platform JWT validation, logging conventions, the compose stack this service joins |
| intent 002 / 001-harvest-service | Not a code dependency — a **pattern** dependency. The grants, the compose entry and the release wiring are done the same way, and deliberately so |

### Depended By

| Unit | Reason |
|------|--------|
| 003, 004, 005, 007 | Everything in this intent runs in this service or reads its schema |

### External Dependencies

| System | Purpose | Risk |
|--------|---------|------|
| MySQL (platform instance) | third schema, third user | Low — the pattern is established; the grants are the only new thing |
| storage-api | capture and approved-image bytes | Medium — this is the first unit to store user-generated binary at volume |

---

## Technical Context

### Suggested Technology

FastAPI + SQLAlchemy 2.x + Alembic, mirroring `backend/` and `harvest/` so all three services read
alike. A sibling directory (`scan/`) with its own `Dockerfile`, joining the existing
`docker-compose.yml` and the existing release workflow as a third image. Image handling with Pillow
for validation and re-encode; fingerprints stored as `BINARY` (phash) and `BLOB` (embedding), with
the vector search strategy deferred to unit 003 — at 50k rows a linear scan is likely sufficient and
that should be measured before an index is introduced.

### Integration Points

| Integration | Type | Protocol |
|-------------|------|----------|
| `elestrals` schema | inbound read | MySQL, read-only grant, cross-schema |
| storage-api | outbound | HTTPS, M2M |
| logs-api | outbound | HTTPS via the established logging path |
| Mobile + web clients | inbound | HTTPS, platform JWT via JWKS |

### Data Storage

| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| `scan_captures` | SQL + object storage | 2M rows / ~800GB at 12 months | until user deletion or curation rejection |
| `scan_predictions` | SQL | ~2–6M rows (up to 3 passes each) | permanent — this is the accuracy record |
| `curation_decisions` | SQL | ~2M rows | permanent |
| `printing_fingerprints` | SQL | 50k rows | rebuildable |

---

## Constraints

- **The grant is the boundary.** `scan-api`'s MySQL user holds no write privilege on `elestrals` or
  `elestrals_harvest`, and neither of the other services holds one on `elestrals_scan`. Verified by a
  test that attempts a write and expects refusal — a boundary nobody tests is a comment.
- **Append-only means append-only.** A curation decision is a new row. A prediction, once written, is
  evidence of what the system claimed to a user, and a later model does not get to revise history.
- **The upload endpoint trusts nothing.** The client crops and strips for privacy; the server verifies
  both and re-encodes regardless. Client-side sanitisation is a privacy feature, never a security
  boundary.
- **A capture is owner-scoped or admin-scoped, never public.** Every repository method takes
  `user_sub` first, as in phase 1.
- **Deletion removes the image and keeps the counters.** A user deleting their captures must not
  silently rewrite the accuracy history the harness computed.
- **Seeded images are countable.** The `source` column exists so the exposure accepted in the ADR can
  be reported as a number at any moment, and seen to be falling.
