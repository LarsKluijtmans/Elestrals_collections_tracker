---
id: 024-scan-experience
unit: 007-scan-experience
intent: 004-card-scanning
type: ddd-construction-bolt
status: planned
stories:
  - 033-capture-and-crop
  - 034-confirm-printing
  - 035-scan-add-to-collection
  - 036-open-card-from-scan
  - 037-batch-scan-session
  - 038-web-camera-entry-mode
created: 2026-08-17T14:51:00Z

requires_bolts: [020-identification-ladder, 021-evaluation-harness, 023-mobile-app-shell]
enables_bolts: []
requires_units: [003-identification-engine, 004-evaluation-and-dataset, 006-mobile-app]
blocks: false

complexity:
  avg_complexity: 3
  avg_uncertainty: 1
  max_dependencies: 3
  testing_scope: 3
---

## Bolt: 024-scan-experience

### Objective

Deliver the thing the user asked for: point a camera at a card, see which one it is, jump to it or
record how many you have — on the phone and in the website, behaving identically.

**This is the minimum shippable increment for collectors.** Nothing before it is visible to a user
except the card images that appear during bolt 022.

### Stories Included

- [ ] **033-capture-and-crop**: The room never leaves the phone - Priority: Must
- [ ] **034-confirm-printing**: Confirm the one thing the camera cannot see - Priority: Must
- [ ] **035-scan-add-to-collection**: Scan, confirm, owned - Priority: Must
- [ ] **036-open-card-from-scan**: Identifying a card is not the same as owning it - Priority: Must
- [ ] **037-batch-scan-session**: A shoebox, not a card - Priority: Should
- [ ] **038-web-camera-entry-mode**: The same flow, in a browser, as a third way in - Priority: Must

### Expected Outputs

- On-device card-bounds crop, EXIF strip and bounded re-encode, identical on both surfaces
- A ranked candidate list with calibrated confidence, printing pre-selection, and finish as the
  visible field in question
- Confirmations **and corrections** recorded as labels against the capture
- Adds through the existing inventory write path with carry-forward condition and ADR-005 undo
- "Open card" as an action distinct from "add"
- A batch session with live camera, running tally, per-add undo, offline queue and conflict surfacing
- The web flow as a third entry mode beside fast-add and the set grid, degrading to file upload
- One shared state machine, two renderings

### Dependencies

#### Bolt Dependencies (within intent)

- **020-identification-ladder** (Required): something to call
- **021-evaluation-harness** (Required): a measured confidence to display
- **023-mobile-app-shell** (Required): a shell to render the mobile half into
- **022-curation-console** (Recommended, not required): candidate lists render an honest empty state
  until images exist, and are markedly better afterwards

#### Unit Dependencies (cross-unit)

- **intent 001 / 003-inventory-core**: the inventory write path, merge-on-duplicate, ADR-005
  delta-adjust undo — all implemented
- **intent 001 / 004-collection-experience**: the carry-forward pattern and the two add surfaces this
  becomes a third mode beside

#### Enables (other bolts waiting on this)

- none — this is the payoff

### Notes

**Scanning is a new caller, not a new inventory semantic.** Merge-on-duplicate, graded copies separate,
`quantity > 0`, `user_sub` scoping — all exist and are tested. Any temptation to add a scan-specific
write path is a sign something is being duplicated.

**Read ADR-005 before writing the undo or the batch queue.** Undo adjusts by a signed delta carrying
an `expected_quantity`, resolved in one compare-and-swap `UPDATE`. That ADR exists because the fast-add
flow fires concurrent requests by design — a batch scan session does the same thing harder, and a
flushing offline queue does it hardest. A client-side read-then-write over `PATCH` reintroduces exactly
the race it eliminated.

**Storing the correction, not just the final state, is the criterion most easily lost.** The natural
implementation writes the chosen printing and moves on. What is needed is *offered* versus *chosen*,
so that "the engine ranked the reverse-foil third and the user picked it" survives — that row is the
most valuable thing this bolt produces for the future recogniser-V2 intent.

**A queued add that conflicts must surface.** Silent dropping is the one failure mode a collector
cannot detect, because they have no independent record of what they scanned.

**Measure the 6s median.** The business goal is time per card in a batch, and it is the number that
decides whether this feature is used at all. Everything upstream can be correct and the product still
fail if entering a box takes as long as typing it.

**A behavioural difference between mobile and web is a bug**, enforced structurally by the shared state
machine rather than caught in review.
