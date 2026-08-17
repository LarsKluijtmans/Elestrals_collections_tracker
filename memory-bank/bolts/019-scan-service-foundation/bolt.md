---
id: 019-scan-service-foundation
unit: 002-scan-service
intent: 004-card-scanning
type: ddd-construction-bolt
status: planned
stories:
  - 005-scan-api-skeleton
  - 006-scan-schema-and-grants
  - 007-capture-store
  - 008-capture-upload-endpoint
  - 009-reference-corpus-and-fingerprints
  - 010-seeded-images-bounded
created: 2026-08-17T14:46:00Z

requires_bolts: [018-pilot-catalog]
enables_bolts: [020-identification-ladder, 021-evaluation-harness, 022-curation-console, 024-scan-experience]
requires_units: [001-pilot-catalog]
blocks: false

complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

## Bolt: 019-scan-service-foundation

### Objective

Stand up `scan-api` — the third backend — with its own schema, its own MySQL user, and grants that
make the isolation real rather than conventional. Then build the two things it exists to hold: the
append-only capture store and the reference corpus.

This follows intent 002's second-backend pattern deliberately and without modification, with one
difference in justification: `harvest-api` is never on a user's request path and `scan-api` always is,
so this service is isolated for **latency** as much as availability.

### Stories Included

- [ ] **005-scan-api-skeleton**: A third deployable backend - Priority: Must
- [ ] **006-scan-schema-and-grants**: Own schema, own user, no write grant on `elestrals` - Priority: Must
- [ ] **007-capture-store**: Every scan retained, append-only, owner-scoped - Priority: Must
- [ ] **008-capture-upload-endpoint**: An upload endpoint that trusts nothing the client says - Priority: Must
- [ ] **009-reference-corpus-and-fingerprints**: Fingerprints with provenance, and a rebuildable index - Priority: Must
- [ ] **010-seeded-images-bounded**: An accepted risk that shrinks instead of accumulating - Priority: Should

### Expected Outputs

- `scan/` service: FastAPI app, config, `/health`, `Dockerfile`, compose entry, release wiring
- `elestrals_scan` schema with its own Alembic tree
- `elestrals_scan_app` MySQL user, with the grant matrix declared in deployment configuration
- **Negative grant tests**: a write to `elestrals` from `scan-api` is attempted and expected to fail
- `scan_captures`, `scan_predictions`, `curation_decisions` — append-only
- `printing_fingerprints` with `source` provenance and a rebuildable index
- Upload endpoint with validation, server-side EXIF verification and re-encode
- Seeded-image policy with a tested purge path
- **ADR-006** — seeded reference images, accepted risk, named owner, review triggers

### Dependencies

#### Bolt Dependencies (within intent)

- **018-pilot-catalog** (Required): something to fingerprint

#### Unit Dependencies (cross-unit)

- **intent 001 / 001-platform-foundation**: JWT validation, logging conventions, the compose stack
- **intent 002 / 001-harvest-service**: a *pattern* dependency, not a code one — the grants, compose
  entry and release wiring are done the same way on purpose

#### Enables (other bolts waiting on this)

- 020-identification-ladder
- 021-evaluation-harness
- 022-curation-console
- 024-scan-experience

### Notes

**The grant is the boundary, and the negative test is the proof.** A missing read grant announces
itself the first time a feature runs. A write grant given by accident announces itself never, until
the day it is used. Both directions are tested.

**This bolt adds the largest new attack surface this project has ever had.** Everything before it
accepted JSON; this accepts arbitrary binary from the internet. Decode with a hard pixel-count
ceiling, re-encode always, and treat the client's crop as a privacy feature rather than a security
boundary.

**ADR-006 must state the exception plainly.** It is a knowing departure from the data model's "we
store a URL, never bytes" note and from ADR-001. This project's own precedent — ADR-004 on robots.txt
— is that a convention broken silently reads as one nobody knew about.

**Do not add a vector index yet.** Measure the linear scan at 50k fingerprints first. ADR-002 set the
precedent when it chose a tiered SQL scan over FULLTEXT for card search: the simpler mechanism was two
orders of magnitude inside budget, and the complex one brought its own failure modes.
