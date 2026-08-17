---
id: 024-consent-capture
unit: 005-curation-console
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:13:00Z'
assigned_bolt: 022-curation-console
implemented: false
---

# Story: 024-consent-capture

## User Story

**As** a collector about to point a camera at my cards
**I want** to be told plainly what happens to the photographs before I take them
**So that** "your pictures may end up on the card pages and in our training data" is something I
agreed to rather than something I discover

## Acceptance Criteria

- [ ] **Given** a first capture upload, **When** it is attempted, **Then** it is preceded by a stated,
      **versioned** consent covering retention, curation, training use, and public display **after
      approval**
- [ ] **Given** an accepted consent, **When** it is recorded, **Then** the accepted version is stored
      per user with a timestamp
- [ ] **Given** the consent, **When** it is presented, **Then** **training** and **public display** are
      separate, separately grantable and separately withdrawable choices
- [ ] **Given** a user who declines display consent, **When** they scan, **Then** scanning works
      normally and their captures are simply never promotable
- [ ] **Given** a user who declines both, **When** they scan, **Then** identification still works and
      the capture is retained only as long as needed to produce the result
- [ ] **Given** a new consent version, **When** a user with an older acceptance uploads, **Then** they
      are asked again rather than assumed to agree
- [ ] **Given** the upload endpoint, **When** a caller has no current consent, **Then** the upload is
      refused with a reason the client can act on

## Technical Notes

Two consents, not one, because they are materially different asks. "Use my photograph to make the
recogniser better" and "show my photograph publicly on a card page" are different in kind, and
bundling them means neither was really agreed to. The FR says so; this story implements it.

**Declining must not break the product.** A user who says no to both still gets a working scanner —
their frames are used to answer their question and then dropped. If declining degraded the feature,
the consent would be coercive and worth nothing as consent.

Versioning is what makes withdrawal and re-asking possible. A consent that is a boolean cannot be
re-sought when the terms change, and the terms here will change — at minimum when the future
recogniser-V2 intent defines what training actually means.

The consent text is a legal artifact, not UI copy, and should be written as one. This story owns the
mechanism; the wording needs a human.

## Dependencies

### Requires
- 008-capture-upload-endpoint

### Enables
- 022-promote-approved-image — promotion requires display consent
- 025-withdrawal-and-takedown
- 017-dataset-versioning — training use requires training consent, per item

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A user grants training but not display | Their captures enter the corpus and the dataset; they are never promotable. Enforced at promotion, not at upload |
| Consent is withdrawn after images are already in a frozen dataset version | Story 025 handles removal; the frozen version records the removal without rewriting its historical metrics (story 017) |
| A user scans before any consent exists in the system | Cannot happen — the upload endpoint refuses without a current consent version |
| The consent version changes mid-batch-session | The session completes under the accepted version; the re-ask happens at the next session rather than interrupting twenty scans |
| A minor is using the app | Out of scope for this story and worth flagging: the platform owns identity and age, and this intent has no age signal of its own |

## Out of Scope

- Writing the legal text
- Age verification — noted above as a real gap, owned by the platform rather than by this intent
