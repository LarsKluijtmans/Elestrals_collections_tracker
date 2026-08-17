---
id: 021-curation-queue
unit: 005-curation-console
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:10:00Z'
assigned_bolt: 022-curation-console
implemented: false
---

# Story: 021-curation-queue

## User Story

**As** the admin
**I want** to see the captured images and what we thought each one was, and remove the ones that do
not actually match
**So that** what survives is a corpus I trust — the images the site will show and the data the next
recogniser will learn from

## Acceptance Criteria

- [ ] **Given** a caller without `elestrals:admin`, **When** any curation route is called, **Then**
      `403` with no body detail — never a `200` with the interesting fields removed
- [ ] **Given** the queue, **When** it is ordered by default, **Then** it surfaces **uncovered
      printings first**, then user corrections, then low-confidence accepts, then everything else
- [ ] **Given** a capture, **When** it is displayed, **Then** it shows the image, what the engine
      predicted, at what confidence, and what the user confirmed
- [ ] **Given** a capture, **When** a decision is made, **Then** it is one of `approve`, `reject` with a
      reason from a closed enumeration, or `relabel` to a different printing
- [ ] **Given** a decision, **When** it is written, **Then** it records who decided and when, as a new
      row that never edits the capture or the prediction
- [ ] **Given** a capture, **When** it is shown to a curator, **Then** the submitter's identity is
      **not** displayed anywhere in the queue
- [ ] **Given** a rejection for containing anything other than a card, **When** it is recorded, **Then**
      it uses a distinct reason and the **image is deleted**, not merely left unapproved
- [ ] **Given** 50k captures, **When** the queue is paged, **Then** a page renders within 400ms p95

## Technical Notes

The ordering is the design. Arrival order treats every capture as equally worth a human's attention,
and they are not: a **relabel** — where the engine said one thing and the user said another — is the
single most valuable row in the system, because it is a labelled example of exactly what the
recogniser gets wrong. An `uncovered_printing` capture is next, because approving it converts a
printing from unmatched to matched for every future user.

Review value is computed, not a sort the admin picks. An admin choosing a sort order will choose
arrival, because it feels complete.

**Why the submitter is hidden.** A curator judging whether a photograph shows the card it claims does
not need to know whose collection it came from. Displaying it makes it available to influence the
judgement, and there is no version of that influence which improves the outcome.

Rejection deletes the image immediately. "Unapproved but retained" is how a store of rejected
photographs of other people's belongings accumulates without anyone ever deciding to keep it.

## Dependencies

### Requires
- 007-capture-store
- 015-calibrated-confidence — ordering by confidence band requires the bands to mean something
- intent 002 / 028-admin-authorisation — the `elestrals:admin` dependency is reused, not rebuilt

### Enables
- 022-promote-approved-image
- 026-rejection-analytics
- 017-dataset-versioning — curated labels feed later versions

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| The user confirmed a printing the engine did not offer | Highest review value. The user found something the candidate list missed entirely |
| An image is technically correct but unusable — blurred, dark, half-cropped | `reject` with a quality reason. Correctness and usability are different judgements and both are the curator's |
| Thousands of near-identical captures of one popular card | Deduplicate in the queue by fingerprint proximity; one representative shown with a count |
| An admin relabels to a printing that does not exist in the catalog | Refused. A relabel points at a printing; it never creates one |
| Two admins decide the same capture concurrently | Both decisions are recorded (append-only); the latest governs, and the disagreement is visible — which is information, not a conflict to suppress |

## Out of Scope

- Promotion to display (story 022)
- Consent and takedown (stories 024, 025)
