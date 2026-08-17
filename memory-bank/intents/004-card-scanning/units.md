---
intent: 004-card-scanning
phase: inception
status: units-decomposed
created: 2026-08-17T12:45:00Z
updated: 2026-08-17T12:45:00Z
---

# Card Scanning — Unit Decomposition

This intent decomposes into **7 units, 38 stories**.

The ordering follows the same principle as intents 001 and 002 — *data before behaviour before
surface* — with one addition specific to this intent: **measurement before display**. The evaluation
harness is scheduled ahead of every user-facing surface, because FR-5's percentages are only honest if
something measured them first, and a surface built before the harness would necessarily ship a
fabricated number.

---

### Unit 001: pilot-catalog

**Description**: The catalog has zero rows. Compile one set by hand, photograph every printing in it,
and find out whether on-device text recognition can read an Elestrals card at all. This unit is the
intent's data floor and its go/no-go, in that order.

**Assigned Requirements**: FR-1

**Stories**:
- 001-compile-pilot-set
- 002-photograph-reference-set
- 003-held-out-evaluation-set
- 004-ocr-feasibility-spike

**Deliverables**:
- FE01 (or the chosen pilot set) compiled as CSV rows through the **existing** importer, importing at
  full coverage rather than as a warning
- A reference photograph per printing, labelled with its `printing_id` at capture time
- A held-out evaluation set, disjoint from the reference corpus by printing *and* by image
- A measured on-device OCR read rate on real photographs — the number that decides whether the rest of
  this intent is worth building

**Dependencies**: Depends on intent 001's card-catalog unit (the importer). Depended by every other
unit — there is nothing to identify against without it.

**Estimated Complexity**: M — the work is manual, the risk is not

---

### Unit 002: scan-service

**Description**: The third backend. `scan-api` as a separately deployable FastAPI service owning
`elestrals_scan`, with its own Alembic tree, its own MySQL user and grants that make the isolation
real. Plus the two things it exists to hold: the append-only capture store and the reference corpus.

**Assigned Requirements**: FR-22, FR-11, FR-16

**Stories**:
- 005-scan-api-skeleton
- 006-scan-schema-and-grants
- 007-capture-store
- 008-capture-upload-endpoint
- 009-reference-corpus-and-fingerprints
- 010-seeded-images-bounded

**Deliverables**:
- `scan-api` service: FastAPI app, config, health endpoint, container, compose and release wiring
- `elestrals_scan` schema and its own Alembic tree
- A third MySQL user with no write grant on `elestrals` or `elestrals_harvest`, verified by a test
  that attempts a write and expects refusal
- `scan_captures`, `scan_predictions`, `curation_decisions` — append-only
- `printing_fingerprints` with `source` provenance (`own_photo` | `approved_capture` | `seeded`)
- Upload endpoint: content-type, magic-byte, dimension and size validation, server-side EXIF
  verification, re-encode at a bounded resolution
- Seeded-image policy: never displayed, deleted on replacement, purge path tested — plus its ADR

**Dependencies**:
- Depends on: 001 (something to fingerprint), intent 001's platform foundation (JWT validation,
  logging conventions, the compose stack)
- Depended by: 003, 004, 005, 007

**Estimated Complexity**: L — a new service is a new service, and the grants are the boundary

---

### Unit 003: identification-engine

**Description**: The recogniser. The ladder that decides how hard to try, the on-device text pass, the
server image pass, the conversion of a score into a confidence a user can act on, and the honest
failure that refuses to guess.

**Assigned Requirements**: FR-2, FR-3, FR-4, FR-5, FR-7

**Stories**:
- 011-catalog-index-for-devices
- 012-on-device-text-pass
- 013-identification-ladder
- 014-server-image-match
- 015-calibrated-confidence
- 016-honest-failure-taxonomy

**Deliverables**:
- A versioned, delta-updatable catalog index (≤8MB) with staleness detection
- A **shared TypeScript** on-device matcher — one implementation consumed by both React Native and the
  browser, so the two surfaces cannot diverge
- Ladder orchestration: ≤3 passes, 90% short-circuit, distinct frame or hint per pass, wall-clock
  budget, per-pass attribution
- Server image match: pHash + embedding nearest neighbour, bounded work, `uncovered` distinguished
  from `not_matched`
- Calibration layer mapping a raw score to a measured confidence band
- The five failure reasons, counted separately, with a pre-filled search fallback

**Dependencies**:
- Depends on: 001 (a corpus to match against), 002 (somewhere to run and something to read)
- Depended by: 004, 007

**Estimated Complexity**: L — this is where the intent's technical risk lives after unit 001

---

### Unit 004: evaluation-and-dataset

**Description**: The unit that makes FR-5 honest. Versioned dataset snapshots, a held-out split that
cannot leak, a harness that measures top-1, top-3 and calibration, and a release gate that refuses an
engine change with no recorded run.

**Assigned Requirements**: FR-15

**Stories**:
- 017-dataset-versioning
- 018-holdout-split
- 019-accuracy-harness
- 020-release-gate-on-harness

**Deliverables**:
- Immutable dataset versions with a manifest, so an accuracy figure names its data
- A split by printing *and* by image, so the same card photographed twice cannot appear on both sides
- Harness reporting top-1, top-3, per-confidence-band accuracy and a predicted-versus-actual
  calibration table
- An exportable dataset version, because the recogniser-V2 intent may not train inside this codebase
- A gate: no engine change ships without a harness run recorded against it

**Dependencies**:
- Depends on: 001 (labelled photographs), 003 (an engine to measure)
- Depended by: 005, 007 — nothing user-facing renders a percentage before this exists

**Estimated Complexity**: M

---

### Unit 005: curation-console

**Description**: The admin half of the flywheel. Review captures, correct or approve them, promote the
good ones to the images the site displays, and hold the consent and takedown machinery that makes
displaying a user's photograph defensible.

**Assigned Requirements**: FR-13, FR-14, FR-17

**Stories**:
- 021-curation-queue
- 022-promote-approved-image
- 023-published-image-projection
- 024-consent-capture
- 025-withdrawal-and-takedown
- 026-rejection-analytics

**Deliverables**:
- `/admin/scan` queue behind `elestrals:admin`, ordered by review value rather than arrival
- `approve` / `reject` with a closed reason / `relabel`, all append-only, submitter identity withheld
- One display image per printing, promoted by an admin, served from storage-api on an immutable key
- `printing_display_images` — the read-only projection the collection backend reads, with the approval
  gate enforced *in the projection* so an unapproved image is not addressable
- Versioned consent, separately withdrawable for training and for display
- Withdrawal and rights-holder takedown paths, both tested rather than promised
- Grouped, counted rejection reasons — the biggest systematic gap visible without reading rows

**Dependencies**:
- Depends on: 002 (captures to curate), 004 (the queue's ordering uses confidence bands that must mean
  something)
- Depended by: none, though 007's candidate lists look much better once images exist

**Estimated Complexity**: L

---

### Unit 006: mobile-app

**Description**: The client that does not exist today. An Expo / React Native app: sign-in against the
platform, a read-only view of the collection, and a release path that reaches a tester's phone without
an app store.

**Assigned Requirements**: FR-18, FR-19, FR-20

**Stories**:
- 027-expo-app-shell
- 028-native-pkce-sign-in
- 029-mobile-collection-browse
- 030-mobile-card-detail-and-completion
- 031-offline-collection-cache
- 032-android-build-and-ota

**Deliverables**:
- Expo app in `mobile/`, TypeScript strict, sharing Zod schemas with the web app and no MUI
- Authorization Code + PKCE against `login-api` on a **separate public client**, redirect
  `elestrals://oauthredirect`, tokens in the platform keystore
- Read-only collection browse and search over the **existing** endpoints, with no mobile-specific
  variant
- Read-only card detail and set completion, including price data where intent 002 has published it
- Last-viewed collection available offline
- CI-built Android artifact, internal distribution, OTA pinned to a native runtime version, version
  reported to the backend

**Dependencies**:
- Depends on: intent 001's platform foundation (branding, i18n, the endpoints it reads)
- Depended by: 007, for the mobile half of the scan experience

**Estimated Complexity**: L — a new client platform, and the only unit with a hard external dependency
(the `login-api` client registration)

---

### Unit 007: scan-experience

**Description**: What the collector actually touches. Capture and crop, the candidate list, the
printing confirmation, the add, the batch session, and the same flow on the web as a third entry mode.
One shared state machine, two renderings.

**Assigned Requirements**: FR-6, FR-8, FR-9, FR-10, FR-12, FR-21

**Stories**:
- 033-capture-and-crop
- 034-confirm-printing
- 035-scan-add-to-collection
- 036-open-card-from-scan
- 037-batch-scan-session
- 038-web-camera-entry-mode

**Deliverables**:
- On-device card-bounds crop, EXIF strip, bounded re-encode — identical on both surfaces
- Candidate list with pre-selected printing and an explicit finish confirmation, recording the
  confirmation *and the correction* as a label
- Add through the existing inventory write path with carry-forward condition and delta-adjust undo
- "Open card" as an action distinct from "add"
- A batch session: live camera, running tally, per-add undo, offline queue with conflict surfacing
- The web camera flow as a third entry mode beside fast-add and the set grid, degrading to file upload

**Dependencies**:
- Depends on: 003 (an engine to call), 004 (a measured confidence to display), 006 (a mobile shell to
  render into)
- Depended by: none — this is the payoff

**Estimated Complexity**: L — the highest UX risk in the intent, as unit 004 was in intent 001

---

## Requirement-to-Unit Mapping

| FR | Requirement | Unit |
|---|---|---|
| FR-1 | Pilot catalog with reference photographs | 001-pilot-catalog |
| FR-2 | The identification ladder | 003-identification-engine |
| FR-3 | On-device pass — text recognition, offline | 003-identification-engine |
| FR-4 | Server pass — image match | 003-identification-engine |
| FR-5 | Ranked candidates with calibrated confidence | 003-identification-engine |
| FR-6 | What a scan resolves, and what the user confirms | 007-scan-experience |
| FR-7 | Honest failure, with a way forward | 003-identification-engine |
| FR-8 | Confirm and record ownership | 007-scan-experience |
| FR-9 | Reach the card from the scan | 007-scan-experience |
| FR-10 | Batch scanning | 007-scan-experience |
| FR-11 | The capture store | 002-scan-service |
| FR-12 | Crop to the card, strip the rest | 007-scan-experience |
| FR-13 | Admin curation queue | 005-curation-console |
| FR-14 | Approved captures become displayed images | 005-curation-console |
| FR-15 | Labelled dataset and evaluation harness | 004-evaluation-and-dataset |
| FR-16 | Seeded reference images, bounded | 002-scan-service |
| FR-17 | Consent, moderation and takedown | 005-curation-console |
| FR-18 | Mobile app signs in against the platform | 006-mobile-app |
| FR-19 | Mobile read-only collection | 006-mobile-app |
| FR-20 | Internal release path | 006-mobile-app |
| FR-21 | The web camera flow | 007-scan-experience |
| FR-22 | The matcher is a third backend | 002-scan-service |

All 22 requirements are assigned to exactly one unit.

> **One boundary worth stating, because it looks like a split and is not.** FR-12 (crop and strip)
> belongs to unit 007, because the crop happens on the device at capture time. Unit 002's upload
> endpoint *verifies* what FR-12 promises — EXIF absence, bounded dimensions — but does not own the
> requirement. The verification is an acceptance criterion of story 008; the behaviour is story 033.
> A privacy control implemented in one place and enforced in another is the normal shape of such a
> control, not a decomposition error.

## Unit Dependency Graph

```text
                     [001 pilot-catalog]         ← the go/no-go
                              │
                     [002 scan-service]
                              │
                  [003 identification-engine]
                              │
                [004 evaluation-and-dataset]     ← the honesty gate
                       ┌──────┴──────┐
                       │             │
          [005 curation-console]     │      [006 mobile-app]
                       │             │             │
                       └─────────────┴─────────────┘
                                     │
                          [007 scan-experience]
```

`001 → 002 → 003 → 004` is a genuine serial chain: there is nothing to identify without a catalog,
nowhere to run without a service, nothing to measure without an engine, and nothing honest to display
without a measurement.

**`006 mobile-app` is the exception, and it is worth exploiting.** It depends only on intent 001's
platform foundation, not on anything in this intent. It can be built in parallel with 002–004 by
anyone not working on the engine, and its one external dependency — the `login-api` client
registration — can be requested on day one rather than discovered on the day the app needs it.

## Execution Order

| Order | Unit | Why here |
|---|---|---|
| 1 | 001 pilot-catalog | Contains the only question that can end the intent: can we read a card? Everything else assumes yes |
| 2 | 002 scan-service | Nothing can be stored, fingerprinted or curated until the service and its grants exist |
| 3 | 003 identification-engine | The recogniser. Second-largest unknown after unit 001 |
| 4 | 004 evaluation-and-dataset | **Before any surface.** A percentage shown to a user before this exists is a fabricated number |
| 5 | 005 curation-console | The flywheel's admin half, and the point at which you judge whether captures are usable |
| 6 | 006 mobile-app | Parallelisable with 2–4; sequenced here only because it is not on the critical path |
| 7 | 007 scan-experience | The payoff. First point at which a collector benefits from any of it |

**Deliberate ordering choice, and the one most likely to be questioned:** unit 004 is scheduled
before both surfaces, which delays the visible product by a bolt. It stays there because FR-5 and
FR-15 are a pair — the first displays a percentage, the second is the only thing that makes the
percentage true. Building the surfaces first would mean shipping a raw model score dressed as an
accuracy claim, then trying to retrofit honesty onto a number users had already been shown. This is
the same reasoning that put intent 002's admin console before its valuation, and it was right there.
