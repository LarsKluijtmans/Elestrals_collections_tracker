---
intent: 004-card-scanning
phase: inception
status: in-progress
created: 2026-08-17T10:00:00Z
completed: null
---

# Inception Log: 004-card-scanning

## Overview

**Intent**: Identify a physical Elestrals card from a camera image, on a new mobile app and in the
existing web app, and record ownership from the result.
**Type**: brown-field — new capability on top of the phase-1 catalog and inventory, plus one
genuinely green-field piece (the mobile client, which does not exist today).
**Created**: 2026-08-17

## Session 1 — 2026-08-17 — intent created

Requested as: *"a mobile app and a feature in the website for scanning cards and identifying them, so
that a user can scan their card, the app shows them which one it is and they can redirect to that
card, and note how many they have."*

Two deliverables, one capability: the identification engine is shared, the surfaces differ.

Read before drafting: `project.yaml`, `standards/tech-stack.md`, `standards/data-model.md`
(catalog and inventory sections), intents 001 (units and decomposition), 002 (requirements, for the
house pattern of spike-first on an unknown), 003 (outline, for scope overlap).

### Numbering

Allocated `004` rather than inserting ahead of `003-marketplace`, because `003` is referenced from
`project.yaml`, `standards/data-model.md` and `decision-index.md`, and renumbering it buys nothing.
Folder number is allocation order; the `phase` field carries intended shipping order and is set at
Checkpoint 2.

### Two constraints found in the existing standards that shape the intent

1. **`printings` is the SKU, and a camera cannot see all of it.** A photograph identifies a card
   face. Rarity is often visually inferable, finish sometimes, edition and language sometimes, but not
   reliably enough to write an inventory row unattended. The design gap between "which card" and
   "which printing" is the first real problem this intent has.
2. **The catalog holds image *URLs*, never bytes** — deliberately, pending permission from the rights
   holder. A server-side visual matcher needs a reference corpus derived from those images. That is
   the same class of question ADR-004 answered for scraping, and it likely needs its own ADR.

### Checkpoint 1 — Clarifying questions ✅

Put in two rounds. Round one asked four decision forks; two came back as selections and two came back
as *notes*, which turned out to be the more valuable answers — they described a system rather than
picking from a menu.

| # | Question | Answer |
|---|---|---|
| 1 | How is the mobile client built? | **Expo / React Native** — a real native app |
| 2 | How is a card recognised? | *No option chosen.* "Is this gonna be accurate enough? I do want to at least try to see what set it's from, the foil… I can accept if we show users multiple cards with percentages" |
| 3 | What does a scan resolve to? | *No option chosen.* "First try the on-device AI, then the server one for a double check, max 3 times, pick the best; if the first is more than 90% sure just go with that" |
| 4 | Scanner companion, or full second client? | **Scanner + read-only collection** |

Answers 2 and 3 together are the **identification ladder** of FR-2: on-device first, ≥90% short-
circuits, escalate to the server pass, at most three passes, ranked candidates with percentages when
nothing clears the bar. Two conditions were added that the user did not state and would have cost a
rewrite later: passes 2 and 3 must use a *different frame or hint* (otherwise they re-ask an identical
question and burn the budget for nothing), and the ladder needs a wall-clock ceiling (otherwise
"3 tries" reads as a broken app).

Round two asked four follow-ups the notes had opened.

| # | Question | Answer |
|---|---|---|
| 5 | How is finish/foil determined? | *No option chosen.* "We are going to make a database with all the captured images and what we thought the card was, later we will transform this into a real labelled data set to train the V2" |
| 6 | How does the flow get condition? | **Carry-forward default**, matching phase-1 fast-add |
| 7 | Where does the reference corpus come from? | **Cache full images, accept the risk** |
| 8 | How to handle the empty catalog? | *No option chosen.* "Let's make a start set ourselves, then add the pictures taken to it, so every scan is either connected to a printing or not connected at all; as the admin I can see these images, remove the ones that don't actually match and save this; the saved and approved images are then shown on the site and used by the AI for future training, testing" |

### The answer that reshaped the intent

Answers 5 and 8 are not scanner requirements — they describe a **data flywheel**, and it is now the
spine of the intent: every scan is retained with what was predicted → an admin curates → approved
captures become both the images the site displays and the labelled corpus a future V2 trains on. The
product improves because it is used, which is the only route to a good recogniser for a TCG nobody
sells a model for.

Three consequences were drawn that the user did not state:

1. **The flywheel answers the foil question for free.** Every user confirmation of a printing *is* a
   finish label. So V1 asks the user (FR-6) rather than shipping a tilt-capture heuristic, and the
   heuristic moves to the V2 intent where it can be *validated* against real labels instead of argued
   for.
2. **Answer 8 largely obviates answer 7, in a good way.** A corpus built from photographs we and our
   users took carries no rights question. So the caching decision was written with an expiry: seed only
   what nobody has scanned, delete the seeded copy when an approved capture replaces it (FR-16). Same
   decision, shrinking liability.
3. **The flywheel does not escape the rights question, only relocates it.** A collector's photograph
   of a card still contains the publisher's artwork; publishing it is a reproduction whoever held the
   camera. FR-14 (display) was therefore split from FR-15 (training) so the display half could be
   withheld without stalling the flywheel. The user then resolved it — see below.

### Checkpoint 2 — Open questions answered, requirements amended

All seven open questions were answered. Five resolved, two deferred out of the intent, one changed the
architecture.

| Question | Answer | Effect |
|---|---|---|
| Native redirect URI for an Expo client? | **Yes** — "just tell me the redirect url to add" | FR-18 resolved. **Verified in the platform source rather than assumed** |
| `elestrals:admin` scope? | **Yes** | FR-13 unblocked — and this resolves the *same* question carried open by intent 002 |
| Publicly display user photographs? | **Yes, after the admin approved the image** | FR-14 resolved, promoted Should → **Must** |
| Store accounts / trademark? | **"Not yet made, this is for the future"** | FR-20 re-cut to internal Android distribution; store submission leaves the intent |
| Finish detection for V2? | **"To be decided later, V2 will be a new intent"** | FR-6's hedge removed; deferred to a future intent |
| Matcher its own service? | **"Matcher is a new service"** | **FR-22 new** — `scan-api`, a third backend |

Six answers arrived for seven questions; the store-accounts answer was read as covering both store
questions. Recorded here because it is an inference, not a statement.

### What the platform source said, which was better than the assumption

FR-18 was written as a *pending platform dependency*. It is not one:

- `login-api/app/services/authorization_service.py:74` validates `redirect_uri` by **exact string
  membership in a JSON allowlist** — no scheme check, no https requirement. A custom scheme is
  accepted as-is.
- `login-api/app/services/token_service.py:84` exchanges an authorization code with `code`,
  `code_verifier`, `redirect_uri`, `client_id` and **no `client_secret`**. Only `client_credentials`
  requires a secret (`token_service.py:205`). The authorization-code grant is already a public-client
  flow.
- PKCE `S256` is mandatory at both ends (`authorization_service.py:76`, `token_service.py:118`).

So the mobile client is the same *kind* of client as the existing web SPA, and FR-18 is a config row
rather than a platform change. The value to register is `elestrals://oauthredirect` on a new public
client. No `elestrals` string appears anywhere in the auth repo source, confirming that client
registration is a runtime console action, consistent with `VITE_LOGIN_CLIENT_ID` being env-supplied.

A constraint was found in the same pass that nobody had asked about: **Android internal distribution
needs no developer account, iOS needs an Apple signing identity even for internal device installs.**
Since the accounts do not exist, Android carries the intent and no requirement completes only on iOS
(FR-20).

## Artifacts Created

| Artifact | Status | File |
|----------|--------|------|
| Requirements | 22 FRs, 7 NFR groups — awaiting Checkpoint 2 approval | `requirements.md` |
| Inception Log | in progress | `inception-log.md` |
| System Context | — | not started |
| Units | — | not started |
| Stories | — | not started |
| Bolt Plan | — | not started |

## Decision Log

| Date | Decision | Rationale | Approved |
|------|----------|-----------|----------|
| 2026-08-17 | Intent numbered `004`, not inserted before marketplace | `003` is referenced from three standards files; folder number is allocation order, `phase` carries shipping order | Yes |
| 2026-08-17 | Expo / React Native, not PWA or Capacitor | Real camera control and on-device recognition are the point; the UI cost is accepted | Yes |
| 2026-08-17 | Identification is a ≤3-pass ladder with a 90% short-circuit | User's design; on-device first keeps the common case free, offline and private | Yes |
| 2026-08-17 | Finish is confirmed by the user in V1, not detected | The confirmation is the label the flywheel needs; detection moves to a V2 intent | Agent call, user-confirmed |
| 2026-08-17 | Every capture is retained and admin-curated into a labelled corpus | User's design; the only route to a recogniser for a TCG nobody sells a model for | Yes |
| 2026-08-17 | Approved captures may be publicly displayed; unapproved may not | Admin approval makes the reproduction deliberate and reviewed rather than automatic | Yes |
| 2026-08-17 | Seeded reference images are bounded and deleted on replacement | Keeps the accepted risk shrinking instead of permanent | Agent call on a user decision |
| 2026-08-17 | **The matcher is a third backend, `scan-api`, owning `elestrals_scan`** | CPU-heavy work on a user latency budget, plus a 800GB corpus, a console and a dataset — none of which belongs in the collection backend. Follows intent 002's FR-13 precedent | Yes |
| 2026-08-17 | Store submission is out of scope; Android internal distribution carries the intent | Developer accounts do not exist and trademark permission is unresolved | Yes |

## Scope Changes

| Date | Change | Reason | Impact |
|------|--------|--------|--------|
| 2026-08-17 | FR-22 added — third backend | Matcher became its own service | Capture store, fingerprints, curation console and dataset move to `elestrals_scan`; FR-14 becomes a publication contract rather than a write; +1 unit |
| 2026-08-17 | FR-14 promoted Should → Must | It is the only route by which the catalog ever has images | Display gate must be enforced in the projection, not just the UI |
| 2026-08-17 | FR-20 re-cut, store submission removed | Accounts do not exist; trademark unresolved | Smaller unit; no App Store or Play dependency anywhere in the intent |
| 2026-08-17 | Automatic finish detection removed | Deferred to a V2 intent | FR-6 simplifies; FR-15 gains a dataset export requirement so the V2 intent can train outside this codebase |

## Ready for Construction

**Checklist**:
- [ ] All requirements documented
- [ ] System context defined
- [ ] Units decomposed
- [ ] Stories created for all units
- [ ] Bolts planned
- [ ] Human review complete

## Next Steps

1. Answer Checkpoint 1 questions
2. Generate full requirements (Checkpoint 2)
3. Generate context + units + stories + bolt plan (Checkpoint 3)
