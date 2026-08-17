---
intent: 004-card-scanning
phase: inception
status: units-defined
created: '2026-08-17T10:00:00Z'
updated: '2026-08-17T12:00:00Z'
---

# Requirements: Card Scanning

> **Amended 2026-08-17**, after all seven open questions were answered at Checkpoint 2. Five were
> resolved, two were deferred out of the intent entirely, and one changed the architecture.
>
> What changed: **FR-22 is new** — the matcher is a third backend, `scan-api`, not a worker pool in
> the collection backend, which moves the capture store, the fingerprints, the curation console and
> the dataset into their own schema and makes FR-14 a publication contract rather than a write.
> **FR-14** is resolved and promoted to Must — public display of approved captures is permitted, on
> the condition that an admin approved it first. **FR-18** is resolved with concrete redirect values
> and turns out to need no platform code change. **FR-20** is re-cut to internal distribution only;
> store submission leaves this intent. **FR-6** loses its V1.5 hedge — finish detection is a future
> intent, not a later story here.

## Intent Overview

Point a camera at a physical Elestrals card and have the app say which card it is — with a stated
confidence, and a ranked short list when it is not sure — then let the collector open that card or
record another copy of it, without typing a name or a collector number.

The capability ships on two surfaces sharing one engine: a **mobile app** (Expo / React Native, new
to this project) and a **camera capture flow in the existing web app**.

It is also, deliberately, a **data-collection system**. Every scan is retained with what we predicted
and what the user confirmed. An admin curates those captures; approved ones become the card images
the site displays and the labelled corpus that trains the next version of the recogniser. The product
gets better because it is used, which is the only way a recogniser for a small TCG ever gets good —
nobody is going to sell us a model that knows Elestrals.

## Why this intent exists

Phase 1 shipped three ways to get a card into a collection — the keyboard-first fast-add flow, the set
grid, and CSV import. All three require the collector to *already know what they are holding* and to
type it. That is the slowest part of entering a shoebox, and it is the part a camera removes.

## The two things this intent must be honest about

**A camera cannot see everything `printings` needs.** Inventory points at a printing: card + rarity +
finish + language + edition. Name, collector number, set and language are readable. Rarity is usually
inferable. **Finish is not readable from a still frame** — foil is a reflectance property, not a
printed one. So the scan identifies as far as the image honestly allows and the user confirms the
rest; that confirmation is also the label the flywheel needs.

**A displayed percentage must be measured, not generated.** A raw model score rendered as "94%" is a
fabricated number, and this project has spent two intents refusing to display fabricated numbers
(intent 002's `ConfidencePill`, FR-4's sold-versus-listed split). Confidence shown to a user is
derived from measured accuracy on a labelled evaluation set, or it is not shown as a percentage.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Speed | Median time from camera open to quantity recorded ≤ 6s per card in a batch session | Must |
| Accuracy | Top-1 card identity ≥ 90% and top-3 ≥ 98% on the evaluation set, for unsleeved undamaged cards | Must |
| Honesty | 100% of displayed confidences derived from measured accuracy; 0 inventory writes below the reject floor without explicit user selection | Must |
| The flywheel turns | ≥ 60% of scanned captures curated to a decision within 30 days; approved captures cover ≥ 80% of pilot-set printings within 90 days of launch | Must |
| Catalog images exist | ≥ 80% of pilot-set printings display an approved image on `/cards/:id` within 90 days | Must |
| Adoption | ≥ 40% of weekly-active collectors use a scan at least once a week | Should |
| Isolation | 0 user-facing incidents in the collection tracker caused by a `scan-api` failure | Must |

---

## Functional Requirements

### FR-1: A pilot catalog with reference photographs
- **Description**: The catalog is empty today — `backend/data/catalog/FE01.csv` ships with zero card
  rows by design (ADR-001). This intent compiles **one** set by hand (FE01, 126 cards) and
  photographs its printings, producing both the corpus the recogniser matches against and the
  labelled set the confidence calibration needs.
- **Acceptance Criteria**: FE01 imports with coverage reported as 126/126 rather than a warning;
  every compiled printing has at least one reference photograph taken by us; each photograph is
  labelled with its `printing_id` at capture time, not inferred later; the evaluation set is
  **disjoint** from the reference corpus, so accuracy is never measured against the images the
  matcher indexed; the compilation is CSV rows through the existing importer, adding no new import
  path.
- **Priority**: Must

> **Why one set and not fifty.** 126 cards is enough to measure real accuracy, calibrate the
> percentages, and prove the ladder end to end. Compiling all ~2,700 by hand before any code runs
> would put the intent's only unknown — does recognition work? — behind months of data entry.

### FR-2: The identification ladder
- **Description**: A capture is resolved by up to three passes with an early exit. Pass 1 runs
  on-device. If its best candidate is at or above the accept threshold, the ladder stops there and no
  image is uploaded for matching. Otherwise the capture escalates to the server pass, and at most one
  further pass after that.
- **Acceptance Criteria**: Pass 1 confidence ≥ 90% ends the ladder immediately; the ladder never
  exceeds 3 passes for one identification attempt; **passes 2 and 3 use a different frame or a hint
  carried from the previous pass** — a pass that would re-ask an identical question against identical
  input is skipped rather than run; the whole ladder completes within its wall-clock budget (NFR
  §Performance) or returns the best candidate it has with a stated `timed_out` reason; every pass
  records which engine produced it, so a result is always attributable; the accept threshold is
  configuration, not a literal, and changing it needs no deploy.
- **Priority**: Must

### FR-3: On-device pass — text recognition, offline
- **Description**: Pass 1 reads the card's title line, collector number, set code and any edition
  stamp using the platform's on-device text recognition, then matches that text against a locally
  held catalog index.
- **Acceptance Criteria**: Pass 1 completes with no network call, including on a phone in airplane
  mode; the local index is downloaded and versioned, and a stale index is detected and refreshed
  rather than used silently; OCR output is fuzzy-matched against the closed catalog vocabulary, so a
  misread character does not fail an otherwise unambiguous card; a read collector number is treated
  as the strongest signal available and, where it uniquely determines a card within a set, the name
  serves as corroboration rather than as an independent vote; no captured image leaves the device on
  a pass-1 accept **except** for the capture-corpus upload of FR-11, which is a separate, stated,
  user-visible action.
- **Priority**: Must

### FR-4: Server pass — image match against the reference corpus
- **Description**: Pass 2 uploads the frame to `scan-api` (FR-22) and matches it against per-printing
  fingerprints — perceptual hashes and embeddings — returning ranked printing candidates with
  distances.
- **Acceptance Criteria**: The endpoint accepts a single cropped frame and returns candidates ranked
  by a score that is converted to a calibrated confidence before display, never shown raw; matching
  is bounded work — a request that cannot complete within its budget returns partial candidates with
  a stated reason rather than holding the connection; the fingerprint index is rebuildable from the
  reference corpus, so a change of algorithm is a re-index and not a data migration; the pass is
  scoped to the printings the corpus actually covers, and a printing with no fingerprint is reported
  as *uncovered* rather than as *not matched* — the two mean different things and only one is the
  matcher's fault.
- **Priority**: Must

### FR-5: Ranked candidates with calibrated confidence
- **Description**: An identification result is a ranked list of candidates, each with a confidence
  the user can act on. A single answer is shown only when one candidate clears the accept threshold.
- **Acceptance Criteria**: Candidates are ordered by confidence and the list is capped at 5; each
  candidate names the card, the set and the printing attributes it is asserting; the displayed
  percentage is the measured accuracy of that engine in that confidence band on the evaluation set,
  within the tolerance in NFR §Accuracy — a raw score is never displayed as a percentage; a result
  set where the top two candidates are within the ambiguity margin is presented as a choice, not as a
  top answer with an alternative buried beneath it; confidence is rendered through the existing
  confidence component from intent 002, so a scan confidence and a price confidence read alike.
- **Priority**: Must

### FR-6: What a scan resolves, and what the user confirms
- **Description**: The scan resolves as far as the image allows — card, set, collector number,
  language, and rarity and edition where visible. **Finish is confirmed by the user**, pre-selected
  to the most likely printing of that card.
- **Acceptance Criteria**: Where a card has exactly one printing, no printing question is asked; where
  it has several, they are offered with the most common pre-selected and finish visibly the field in
  question; the pre-selection is never committed silently — the add action is the user's; the
  confirmed printing is recorded against the capture as a label (FR-11), including when the user
  changes it, because a correction is the most valuable label the system can receive; condition is
  **not** inferred from the image under any confidence.
- **Priority**: Must

> **Automatic finish detection is out of scope, by decision.** A two-frame tilt capture can detect
> foil from the way a specular highlight moves, and a model trained on flywheel labels could learn it.
> Both belong to a **future intent** covering recogniser V2 — decided 2026-08-17 — not to a later
> story here. What this intent owes that intent is the labelled data: every user confirmation above,
> including every correction, is a finish label recorded at the moment it is made.

### FR-7: Honest failure, with a way forward
- **Description**: When no candidate clears the reject floor, the scan says so and hands the user the
  existing search flow rather than showing its least-bad guess.
- **Acceptance Criteria**: A result with no candidate above the reject floor renders as "no confident
  match", never as a ranked list of noise; the failure state offers search by name and manual entry,
  pre-filled with any text the OCR did read; the capture is still stored (FR-11) with its failure
  reason, because unmatched captures are the queue of what the corpus and the catalog are missing;
  distinguishable reasons are reported and counted separately — `no_text_read`, `no_catalog_match`,
  `uncovered_printing`, `below_floor`, `timed_out`.
- **Priority**: Must

### FR-8: Confirm and record ownership
- **Description**: From a confirmed identification, record ownership: printing, condition, quantity.
- **Acceptance Criteria**: Condition uses a **session carry-forward** default — the last condition
  used, shown persistently and changeable in one tap, matching the phase-1 fast-add behaviour;
  quantity defaults to 1 with a single-tap increment; the write goes through the existing inventory
  write path on the collection backend and inherits its merge-on-duplicate invariant — scanning is a
  new *caller*, not a new inventory semantic, and `scan-api` never writes inventory; scanning the same
  card twice in a session increments rather than creating a second row; every scanned add is undoable
  through the existing delta-adjust endpoint (ADR-005) and the undo carries the quantity it expects.
- **Priority**: Must

### FR-9: Reach the card from the scan
- **Description**: From a scan result, open that card's detail page.
- **Acceptance Criteria**: The result offers the card page as an action distinct from adding, because
  identifying a card and owning a card are different intentions; on mobile the card page is the
  read-only detail view of FR-19; on web it is the existing `/cards/:id`; navigating away does not
  discard an in-progress batch session.
- **Priority**: Must

### FR-10: Batch scanning
- **Description**: A scan session stays open and takes card after card, with a running tally, so a
  box is entered without returning to a menu between cards.
- **Acceptance Criteria**: The camera stays live after an add; the session shows a running count and
  the carry-forward condition at all times; each add is individually undoable from the session list
  without leaving the camera; a session survives a backgrounded app and a lost network — adds queue
  locally and reconcile, and a queued add that later conflicts surfaces rather than being dropped;
  ending a session reports what was added and what failed.
- **Priority**: Should

### FR-11: The capture store — every scan retained with its prediction and its outcome
- **Description**: Each capture is stored in `scan-api`'s own schema: the image, the engine passes
  that ran, the candidates each returned, the confirmed printing if any, and the failure reason if
  not. This is the raw material of the flywheel.
- **Acceptance Criteria**: A capture is written for every scan attempt, accepted or failed, and is
  linked to exactly one printing **or** to none — there is no partial or guessed linkage; the stored
  prediction is what was actually shown to the user, so a later model change cannot rewrite history;
  the user's confirmation or correction is recorded as the provisional label with its provenance
  (`user_confirmed`) distinct from an admin decision (`admin_approved`); the store is append-only in
  the same sense as `price_observations` — a curation decision is a new row and never an edit to the
  capture; captures are readable by their owner and by an admin, and by nobody else; a user can delete
  their own captures, and deletion removes the image while retaining the anonymous outcome counters
  that accuracy measurement depends on.
- **Priority**: Must

### FR-12: Crop to the card, strip the rest
- **Description**: Only the card is stored. The frame around it — table, hands, room, faces — is
  discarded before the image is persisted, and camera metadata is removed.
- **Acceptance Criteria**: Card-bounds detection runs **on the device**, before upload, and the
  uploaded payload contains the cropped region only; EXIF is stripped, GPS unconditionally, and
  stripping is verified server-side rather than trusted from the client; a capture whose card bounds
  cannot be found is rejected client-side with guidance, not uploaded whole "just in case"; the
  cropped image is re-encoded at a bounded resolution and size (NFR §Performance) so the corpus
  cannot be filled with 12-megapixel frames.
- **Priority**: Must

### FR-13: Admin curation queue
- **Description**: An admin reviews captures, confirms or corrects the printing, and approves images
  into the reference corpus — or rejects them.
- **Acceptance Criteria**: Requires the `elestrals:admin` scope, through the same single dependency as
  intent 002's admin routes; the queue is orderable by what is worth reviewing rather than only by
  arrival — uncovered printings, corrections where the user disagreed with the model, and low-
  confidence accepts surface first, because those are where the labels are worth most; a decision is
  one of `approve`, `reject` with a reason, or `relabel` to a different printing; approving records
  who approved it and when; rejection reasons are a closed enumeration and are counted, so the biggest
  systematic failure is visible without reading rows; an image containing anything other than a card
  is rejected with a distinct reason and its image deleted rather than merely unapproved; the queue
  never shows who submitted a capture — curation is about the card, and the reviewer does not need the
  collector's identity to judge it.
- **Priority**: Must

### FR-14: Approved captures become the catalog's displayed images
- **Description**: An approved capture is promoted to the image shown for that printing on the site,
  filling the gap left by a catalog that stores URLs and currently has none. **Public display is
  permitted only after an admin has approved the image** — decided 2026-08-17.
- **Acceptance Criteria**: Exactly one approved image per printing is marked as the display image, and
  it is replaceable; **no image is displayed to any user before an admin approval exists** — the
  approval is the gate, enforced in the published projection rather than only in the UI, so a client
  cannot request an unapproved image by id; the display image is served from storage-api with an
  immutable object key, the path already anticipated by the data model's image-rights note; `scan-api`
  publishes approved display images as a read-only projection the collection backend reads, and does
  **not** write to the `elestrals` schema (FR-22); a printing with no approved image renders the
  existing honest empty state, never a placeholder that implies the image is missing by accident;
  promotion is an admin action and never automatic, because a technically correct match can still be
  an unusable photograph; the contributor is credited or anonymous by their own choice.
- **Priority**: Must

> **Resolved, with the condition recorded.** A collector's photograph of a card still contains the
> publisher's artwork, so displaying it publicly is a reproduction whoever pressed the shutter. The
> decision taken on 2026-08-17 is that this is acceptable **once an admin has approved the image**,
> which makes the exposure deliberate and reviewed rather than automatic and unbounded. The risk
> acceptance, its owner and its review triggers go in an ADR alongside FR-16's, in the mould of
> ADR-004. Promoted from Should to Must because it is the only route by which the catalog ever has
> images at all.

### FR-15: The labelled dataset and the evaluation harness
- **Description**: Curated captures accumulate into a versioned labelled dataset, and a repeatable
  harness measures the recogniser against a held-out slice of it. This is what makes FR-5's
  percentages real, and it is what a future V2 intent trains on.
- **Acceptance Criteria**: A dataset version is an immutable snapshot with a manifest, so an accuracy
  figure names the data it was measured on; the evaluation slice is held out and never indexed into
  the matching corpus, and the split is by *printing* as well as by image so the same card
  photographed twice cannot appear on both sides; the harness reports top-1 and top-3 accuracy
  overall and per confidence band, plus a calibration table of predicted-versus-actual; a released
  change to either engine cannot ship without a harness run recorded against it; the harness runs on
  the pilot set from the day FR-1 completes, so there is never a period during which accuracy is
  asserted rather than measured; a dataset version is exportable, because the V2 intent that trains
  on it may not run inside this codebase.
- **Priority**: Must

### FR-16: Seeded reference images — an accepted risk, bounded and shrinking
- **Description**: Printings that nobody has photographed yet have no fingerprint and cannot be
  matched by the server pass. To cold-start beyond the pilot set, reference images may be cached and
  fingerprinted. This is a knowing exception to the data model's "URLs never bytes" rule and to
  ADR-001, and it requires an accepted-risk ADR with a named owner in the mould of ADR-004.
- **Acceptance Criteria**: A seeded image is flagged `source = 'seeded'` and is distinguishable from
  an `own_photo` or an `approved_capture` at the row level, so the exposure is always countable;
  a seeded image is **never displayed** to any user, admin included — it exists to be fingerprinted;
  once a printing has an approved capture, the seeded image is deleted and its fingerprint rebuilt
  from the approved one, so the count of seeded images trends to zero as the flywheel turns; the ADR
  names the risk owner and the review triggers; a seeded image can be purged on request per source,
  per set or wholesale, and the purge path is tested rather than assumed.
- **Priority**: Should

> **Recorded because it was chosen deliberately.** The alternative — fingerprint only what we and our
> users photographed — carries no rights question at all, and the flywheel reaches the same place more
> slowly. Caching was chosen to avoid a cold start; the bounding and the expiry are the conditions on
> that choice, not decoration.

### FR-17: Consent, moderation and takedown for submitted images
- **Description**: Users submit photographs. Those photographs may be published after approval and
  used for training, so the terms must say so, and there must be a way out.
- **Acceptance Criteria**: Capture upload is preceded by a stated, versioned consent covering
  retention, curation, training use and possible public display after approval, and the accepted
  version is recorded per user; consent for *training* and consent for *public display* are separately
  withdrawable, because they are materially different asks; withdrawal removes the image from the
  corpus and from any display within a stated window and is verified by a test, not by a promise; an
  image that reaches the queue containing a person or anything other than a card is rejected and
  deleted under FR-13; a takedown request from a rights holder can remove a printing's images
  site-wide in one action.
- **Priority**: Must

### FR-18: The mobile app signs in against the platform
- **Description**: A native Expo / React Native client authenticating through the platform's
  `login-api` with Authorization Code + PKCE, holding no secret. **Verified 2026-08-17 to need no
  platform code change** — only a client registration.
- **Acceptance Criteria**: A **new public client** is registered on `login-api`, separate from the web
  SPA's client so that revoking one does not affect the other, with `redirect_uris` containing exactly
  `elestrals://oauthredirect` and `allowed_grant_types` of `authorization_code` and `refresh_token`
  but **not** `client_credentials`; the app sends `code_challenge_method=S256`, which `login-api`
  requires, and sends a `redirect_uri` byte-identical to the registered string at both `/authorize`
  and `/token` — it is validated in both places; tokens are stored in the platform keystore (Keychain
  / Keystore), never in `AsyncStorage`; refresh is silent and a failed refresh returns to sign-in
  without losing a queued batch session; the app holds the public `client_id` only, and no M2M
  credential ever reaches the device; the same JWT validation and `user_sub` scoping serves mobile and
  web, so mobile adds no new trust path into either backend; theme and language come from the same
  resolved branding and i18n sources as the web app.
- **Priority**: Must

> **Verified against the platform source, not assumed.** `authorization_service.py:74` matches
> `redirect_uri` by exact string membership in a JSON allowlist with no scheme restriction, so a
> custom scheme is accepted. `token_service.py:84` exchanges an authorization code with **no
> `client_secret`** — only `client_credentials` requires one (`token_service.py:205`). PKCE `S256` is
> mandatory at both ends. The mobile client is therefore the same *kind* of client as the existing web
> SPA, and this requirement is a config row rather than a platform change.

### FR-19: The mobile app's read-only collection
- **Description**: Beyond scanning, the app answers "do I already own this?" — browse and search the
  collection, and view set completion and card detail. Read-only: all editing stays on the web app.
- **Acceptance Criteria**: Collection browse and search reuse the existing endpoints with no
  mobile-specific variant; set completion is displayed, not recomputed on the device; card detail is
  read-only, including price data where intent 002 has published it; no editing, bulk action,
  import/export, settings or admin surface exists in the app, and their absence is by construction
  rather than by hiding a button; the last-viewed collection state is available offline so a card shop
  with no signal is not a dead app.
- **Priority**: Must

### FR-20: An internal release path for the mobile app
- **Description**: The app can be built reproducibly and distributed to testers. **Public store
  submission is out of scope for this intent** — the developer accounts do not exist, and the
  trademark question that gates a store listing is unanswered.
- **Acceptance Criteria**: A reproducible build produces an **Android** artifact from CI, not from a
  laptop, and installs on a tester's device with no developer account of any kind; the iOS build is
  defined and buildable but is **explicitly gated on an Apple signing identity** and is not a
  precondition for this intent completing; JS-only updates ship over the air, and the over-the-air
  channel is pinned to a native runtime version so an update cannot land on an incompatible binary;
  the app reports its version and build to the backend so a bug report identifies what was running;
  the release path is documented alongside the platform's existing compose-based deployment rather
  than invented separately; no requirement here depends on an App Store or Play listing.
- **Priority**: Must

> **Re-cut 2026-08-17.** Android internal distribution needs no developer account, so it carries the
> whole intent. iOS needs an Apple signing identity even for internal device installs, which does not
> exist yet. Store listing — and the trademark permission it requires — moves to a future intent
> together with the accounts.

### FR-21: The web camera flow
- **Description**: The existing web app gains camera capture, using the same engine, the same
  contract and the same confirmation flow.
- **Acceptance Criteria**: Capture uses the browser camera and degrades to file upload where camera
  access is unavailable or refused; the identification contract is **identical** to mobile's — the
  same `scan-api` endpoint, the same candidate shape, the same calibrated confidence — so a divergence
  in behaviour between surfaces is a bug rather than a platform difference; the on-device pass runs in
  the browser where support allows and otherwise escalates to the server pass immediately, reporting
  which passes ran; cropping and EXIF stripping (FR-12) apply identically in the browser; the flow is
  reachable from the existing add-to-collection surfaces as a third entry mode beside fast-add and the
  set grid.
- **Priority**: Must

### FR-22: The matcher is a third backend
- **Description**: Identification runs as its own deployable service, **`scan-api`**, owning the
  `elestrals_scan` schema on the same MySQL instance. It reads the catalog cross-schema, read-only,
  holds the fingerprints, the captures, the curation decisions and the dataset, and publishes approved
  display images for the collection backend to read. Decided 2026-08-17, replacing a bounded worker
  pool inside the collection backend.
- **Acceptance Criteria**: `scan-api` has its own container, its own Alembic tree and its own schema;
  it holds **no write grant** on the `elestrals` schema, enforced by the database user's privileges
  rather than by convention, and the collection backend holds no write grant on `elestrals_scan`;
  clients call `scan-api` **directly** for identification rather than through a proxy, and it validates
  the same platform JWT via JWKS with the same `user_sub` scoping, so it adds no new trust path;
  `scan-api` being down degrades scanning to the on-device pass and returns no error from any
  `/collection` request; the approved-display-image projection is the **only** `scan-api` data the
  collection backend reads, exposed as a read-only view or published table and never as a join into
  `scan-api`'s private tables; all three services are brought up by the same compose stack and the
  same release workflow.
- **Priority**: Must

> **Why a third service and not a worker pool.** Embedding and matching are CPU-heavy on a user's
> latency budget, and the capture corpus grows to hundreds of gigabytes with a curation console and a
> dataset pipeline attached — none of which the collection backend should carry. This follows intent
> 002's FR-13 precedent exactly, including the grant-enforced boundary and the single published
> contract, with one deliberate difference: `harvest-api` is never on a user's request path and
> `scan-api` always is, so its isolation requirement is about *latency* as much as availability.

---

## Non-Functional Requirements

### Accuracy

The distinguishing NFR group of this intent. Every figure here is measured by FR-15's harness against
a named dataset version, and a release that cannot produce these numbers has not met the requirement.

| Requirement | Metric | Target |
|---|---|---|
| Card identity, top-1 | unsleeved, undamaged, pilot set | ≥ 90% |
| Card identity, top-3 | same | ≥ 98% |
| Printing identity, top-1 | after user finish confirmation | ≥ 95% |
| Calibration | displayed confidence vs measured accuracy in that band | within ±10 percentage points |
| False confident accept | share of ≥ 90% accepts that were wrong | ≤ 2% |
| Silent wrong writes | inventory rows written below the reject floor without user selection | 0 |

### Performance

| Requirement | Metric | Target |
|---|---|---|
| On-device pass | p95, mid-range phone | < 800ms |
| Server pass, corpus of 50k fingerprints | p95 | < 1.2s |
| Full ladder, worst case 3 passes | p95 | < 2.5s |
| Camera open to first candidate | p95 | < 1.5s |
| Uploaded cropped frame | size | ≤ 400KB, ≤ 1600px on the long edge |
| Local catalog index download | size | ≤ 8MB, delta-updatable |
| Admin curation queue page | p95 | < 400ms |
| Batch session add | perceived | optimistic, reverting visibly on failure |

### Scalability

| Requirement | Metric | Target (12-month) |
|---|---|---|
| Captures stored | rows | 2M |
| Capture image storage | bytes | 800GB at 400KB p95 |
| Printing fingerprints | rows | 50,000 |
| Approved corpus images | rows | 150,000 |
| Concurrent scan sessions | sessions | 500 |

### Security & Authorisation

| Requirement | Standard | Notes |
|---|---|---|
| Capture ownership | `user_sub` from the validated JWT | a capture is readable by its owner and an admin; every repository method takes `user_sub` first, as in phase 1 |
| Curation | `elestrals:admin` scope | confirmed available 2026-08-17; the same single dependency as intent 002's admin routes; `403` with no body detail, never a filtered `200` |
| Service isolation | database grants | `scan-api` has no write grant on `elestrals`; the collection backend has none on `elestrals_scan` |
| Mobile credentials | public `client_id` only | no M2M secret on a device, ever; tokens in the platform keystore |
| Upload validation | content type, magic bytes, dimensions, size | an upload endpoint is an attack surface; a decoded image is re-encoded server-side before storage |
| Server-side crop verification | enforced | client-side cropping is a privacy feature, not a security boundary |
| Unapproved images | not addressable | the approval gate lives in the published projection, so an unapproved image cannot be fetched by id |
| Identity in curation | withheld | the admin queue shows the card, never the submitter |

### Privacy

| Requirement | Standard | Notes |
|---|---|---|
| Frame contents | cropped to card bounds on-device before upload | the room, the hands and the faces never leave the phone |
| Camera metadata | EXIF stripped, GPS unconditionally | verified server-side |
| Consent | versioned, recorded, separately withdrawable for training and for display | two materially different asks |
| Deletion | user deletes their captures; image removed, anonymous outcome counters retained | accuracy history survives without the image |
| Retention | a rejected capture's image is deleted at curation, not retained "just in case" | |

### Reliability

| Requirement | Metric | Target |
|---|---|---|
| Offline scanning | on-device pass with a current index | fully functional, adds queue locally |
| `scan-api` unavailable | behaviour | ladder degrades to on-device only, states that it did, never blocks the add, and never fails a `/collection` request |
| Queued adds | after reconnect | reconciled; a conflicting queued add surfaces rather than being dropped |
| Corpus rebuild | fingerprint index from stored images | fully regenerable |
| Backgrounded app | batch session | survives and resumes |

### Compliance

| Requirement | Standard | Notes |
|---|---|---|
| Reference image rights | accepted risk, named owner, bounded and shrinking (FR-16) | requires a new ADR; amends `data-model.md`'s "URLs never bytes" note and qualifies ADR-001 |
| Published user images | permitted **after admin approval** (FR-14) | decided 2026-08-17; the risk acceptance and its owner are recorded in an ADR |
| User-generated content | consent, moderation, takedown (FR-17) | required before any capture is displayed publicly |
| Store distribution | out of scope | no store listing in this intent, so the trademark question does not gate it |
| No recurring data cost | inherited from ADR-004 | rules out a paid third-party recognition API; the engine is ours |

---

## Constraints

### Technical Constraints

**Project-wide standards**: loaded from `memory-bank/standards/` by the Construction Agent.

**Intent-specific:**
- **Expo / React Native joins the tech stack.** A new entry in `standards/tech-stack.md` with its own
  build and release path. TypeScript types and Zod schemas are shared with the web app; **MUI
  components are not** — the mobile UI is built, not ported. This is accepted as the price of a real
  camera and on-device recognition.
- **Three backends, one MySQL instance, three schemas.** `scan-api` owns `elestrals_scan`;
  `harvest-api` owns `elestrals_harvest`; `elestrals` stays owned by the collection backend. Separate
  Alembic trees; no service migrates another's schema. Cross-schema reads are read-only and
  one-directional in each case.
- **One identification contract, two callers.** The endpoint, the candidate shape and the confidence
  semantics are identical for mobile and web. A behaviour that differs between surfaces is a defect.
- **Capture rows are append-only.** A curation decision is a new row. A prediction, once shown to a
  user, is history and is not rewritten by a later model.
- **No figure without its confidence**, and no confidence that is not measured — FR-5 and FR-15 are a
  pair, and the second is what makes the first honest.
- **Android carries the mobile intent; iOS is defined but gated.** No requirement completes only on
  iOS.
- **Two ADRs are required before construction**: the seeded-reference-image accepted risk (FR-16), and
  the public display of user-submitted card photographs after approval (FR-14). Both amend the data
  model's image-rights note. ADR numbering continues from ADR-005.

### Business Constraints
- **No recurring data cost** (ADR-004). No paid recognition API, no per-scan vendor fee.
- **The pilot set is compiled by hand** and not scraped (ADR-001). The scanner's coverage is bounded by
  that work, and that is accepted rather than worked around.
- **No app store presence in this intent.** Developer accounts do not exist and the trademark question
  is unanswered; internal Android distribution is the path that depends on neither.

---

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|---|---|---|
| On-device OCR reads an Elestrals card's name and collector number reliably enough for a closed-vocabulary match | The whole ladder rests on pass 2, latency triples and offline scanning dies | Verified on real photographs during the pilot unit, before the mobile app is built. This is the intent's spike and it comes first |
| Collector number plus set uniquely determines a card in our catalog | Candidate lists stay ambiguous where they should be certain | Already true of the schema — `UNIQUE (set_id, collector_number)`. Verified against the compiled pilot set |
| Users will confirm a printing rather than abandoning the flow at the extra tap | The flywheel receives no finish labels and the V2 intent has nothing to train on | Pre-selection makes the common case one tap; the tap is measured, and a high abandonment rate becomes evidence for the V2 intent rather than a change here |
| Enough users scan enough cards to grow the corpus | Coverage stays at whatever we photographed ourselves | The pilot set is fully photographed by us, so the product works at launch without any user contribution |
| A cropped card photograph is enough for reliable image matching | Pass 2's accuracy target is unreachable and the ladder is OCR-only in practice | Measured by FR-15's harness on the pilot set before the corpus is grown beyond it |
| ~~The platform can issue an `elestrals:admin` scope~~ | — | **Resolved 2026-08-17: yes.** This also resolves the same question carried open by intent 002 |
| ~~`login-api` can register a native redirect URI~~ | — | **Resolved 2026-08-17: yes**, and verified in the platform source — exact-string allowlist, no scheme restriction, and the code exchange needs no client secret |

---

## Open Questions

| Question | Owner | Due | Resolution |
|---|---|---|---|
| Can `login-api` register a native redirect URI for an Expo client? | Lars | — | **Resolved 2026-08-17** — yes. `elestrals://oauthredirect` on a new public client; verified against `authorization_service.py:74` and `token_service.py:84` |
| Can the platform issue an `elestrals:admin` scope? | Lars | — | **Resolved 2026-08-17** — yes. Also unblocks intent 002's FR-14 and bolt 013 |
| May we publicly display user-submitted photographs of copyrighted cards? | Lars | — | **Resolved 2026-08-17** — yes, **after admin approval**. Recorded as an accepted risk in an ADR |
| Does the matcher need its own service? | Lars | — | **Resolved 2026-08-17** — yes. `scan-api`, third backend, own schema (FR-22) |
| Store listing, developer accounts, and trademark permission | Lars | future intent | **Deferred 2026-08-17** — accounts do not exist; store distribution leaves this intent |
| Automatic finish detection — tilt heuristic or a trained model | Lars | future intent | **Deferred 2026-08-17** — recogniser V2 is its own intent; this intent produces its training data |
| Does an Apple signing identity become available, and under what entity? | Lars | before an iOS build ships | **Pending** — does not gate this intent completing (FR-20) |
| Which Elestrals set is the pilot — FE01, or one you own more completely? | Lars | before unit 001 | **Pending** — FE01 assumed; a set you can photograph end to end is worth more than the first set numerically |

---

## Traceability

FR → story traceability is established in `units.md` and the per-unit story files, and this section is
filled in when decomposition completes. No FR may reach Checkpoint 3 without at least one story.
