---
id: 022-curation-console
unit: 005-curation-console
intent: 004-card-scanning
type: ddd-construction-bolt
status: planned
stories:
  - 021-curation-queue
  - 022-promote-approved-image
  - 023-published-image-projection
  - 024-consent-capture
  - 025-withdrawal-and-takedown
  - 026-rejection-analytics
created: 2026-08-17T14:49:00Z

requires_bolts: [019-scan-service-foundation, 021-evaluation-harness]
enables_bolts: [024-scan-experience]
requires_units: [002-scan-service, 004-evaluation-and-dataset]
blocks: false

complexity:
  avg_complexity: 3
  avg_uncertainty: 1
  max_dependencies: 3
  testing_scope: 3
---

## Bolt: 022-curation-console

### Objective

Build the admin half of the flywheel: review captures, correct or approve them, promote the good ones
to the images the site displays, and put in place the consent and takedown machinery that makes
displaying a collector's photograph defensible.

This is also the bolt where the catalog finally gets images. It has stored image URLs since launch and
has never held one.

### Stories Included

- [ ] **021-curation-queue**: Judge the captures that are worth judging first - Priority: Must
- [ ] **022-promote-approved-image**: The catalog gets its first images - Priority: Must
- [ ] **023-published-image-projection**: One read-only contract, and no way around it - Priority: Must
- [ ] **024-consent-capture**: Say what will happen to the photograph, before it is taken - Priority: Must
- [ ] **025-withdrawal-and-takedown**: A way out, tested rather than promised - Priority: Must
- [ ] **026-rejection-analytics**: What the recogniser is systematically getting wrong - Priority: Should

### Expected Outputs

- `/admin/scan` queue behind `elestrals:admin`, ordered by computed review value
- `approve` / `reject` with a closed reason / `relabel`, append-only, submitter withheld
- One display image per printing, promoted by explicit admin action, on an immutable storage-api key
- `printing_display_images` — the read-only projection, with the approval gate enforced **in the
  projection**
- Versioned consent, separately withdrawable for training and for display
- Withdrawal and rights-holder takedown paths, both with tests that assert removal from all four
  places an image lives
- Grouped rejection counts and confusion pairs
- **ADR-007** — public display of user-submitted card photographs after admin approval

### Dependencies

#### Bolt Dependencies (within intent)

- **019-scan-service-foundation** (Required): captures to curate
- **021-evaluation-harness** (Required): queue ordering by confidence band needs the bands to mean
  something

#### Unit Dependencies (cross-unit)

- **intent 002 / 005-admin-console**: the `elestrals:admin` dependency, the admin SPA section and its
  code-splitting are reused rather than rebuilt

#### Enables (other bolts waiting on this)

- 024-scan-experience — not blocking, but candidate lists with images are markedly more usable

### Notes

**The ordering is the design.** Arrival order treats every capture as equally worth a human's
attention. A **relabel** — engine said one thing, user said another — is the single most valuable row
in the system, because it is a labelled example of exactly what the recogniser gets wrong. Uncovered
printings come next, because approving one converts a printing from unmatched to matched for every
future user.

**ADR-007 records a real exposure with a real condition.** A collector's photograph of a card contains
the publisher's artwork; publishing it is a reproduction whoever pressed the shutter. The decision
taken on 2026-08-17 was yes, **conditional on admin approval** — which is what makes it reviewed
rather than automatic. The ADR names the risk owner and the review triggers, in ADR-004's form.

**The approval gate belongs in the projection, not the UI.** Enforcing it in an API filter leaves the
object one guessed id away from being public. In the projection, an unapproved image has no path to a
user at all.

**Withdrawal must be tested, not promised.** It is the requirement most likely to be exercised by
someone already upset, and a deletion path that has never run is a promise. The test asserts the image
is gone from the projection, from storage, from the corpus, and excluded from the next dataset
version — four places, because that is how many it went to.

**This bolt is also a judgement gate.** If curation shows the corpus filling with unusable
photographs, that is worth knowing before bolt 024 ships the flow that generates them to everyone.
