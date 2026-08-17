---
id: 023-mobile-app-shell
unit: 006-mobile-app
intent: 004-card-scanning
type: simple-construction-bolt
status: planned
stories:
  - 027-expo-app-shell
  - 028-native-pkce-sign-in
  - 029-mobile-collection-browse
  - 030-mobile-card-detail-and-completion
  - 031-offline-collection-cache
  - 032-android-build-and-ota
created: 2026-08-17T14:50:00Z

requires_bolts: []
enables_bolts: [024-scan-experience]
requires_units: []
blocks: true

complexity:
  avg_complexity: 2
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 2
---

## Bolt: 023-mobile-app-shell

### Objective

Build the client that does not exist: an Expo / React Native app that signs in against the platform,
shows the collection read-only, and reaches a tester's phone without an app store.

The app is deliberately narrow — a scanner with a collection you can look at, not a second copy of the
product. Read-only is load-bearing: every editing surface added here must be built twice forever.

### Parallelisable — start it early

**This bolt depends on nothing else in intent 004.** It can run alongside bolts 018–021 by anyone not
working on the recogniser. Its one external dependency — the `login-api` client registration — is
already resolved and should be requested on day one rather than discovered on the day the app needs
it.

### ⚠ Blocked-on warning

`blocks: true` — stories **029, 030 and 031** depend on intent 001's `/collection` endpoints, built by
**bolt 006**, which is `planned` and **not built**. Before starting those stories, confirm bolt 006
has shipped. If it has not, the correct response is to say so and reorder, **not** to invent a
bespoke mobile collection endpoint that would later have to be reconciled.

Stories 027, 028 and 032 are unblocked and can proceed regardless.

### Stories Included

- [ ] **027-expo-app-shell**: An app that builds, themes and speaks two languages - Priority: Must
- [ ] **028-native-pkce-sign-in**: Sign in on a phone, holding no secret - Priority: Must
- [ ] **029-mobile-collection-browse**: Do I already own this? - Priority: Must — **blocked on intent 001 bolt 006**
- [ ] **030-mobile-card-detail-and-completion**: The card, read-only, with its price if we have one - Priority: Must
- [ ] **031-offline-collection-cache**: A card shop with no signal is not a dead app - Priority: Should
- [ ] **032-android-build-and-ota**: On a tester's phone, without a store - Priority: Must

### Expected Outputs

- Expo app in `mobile/`, TypeScript strict, sharing Zod schemas with the web app, no MUI
- PKCE sign-in against a **new public client** with redirect `elestrals://oauthredirect`, tokens in the
  platform keystore
- Read-only collection browse, search, card detail and set completion over **existing** endpoints
- Offline availability of the last-viewed collection, with visible staleness
- CI-built Android artifact, internal distribution, OTA pinned to a native runtime version
- Version and build reported to the backend

### Dependencies

#### Bolt Dependencies (within intent)

- none

#### Unit Dependencies (cross-unit)

- **intent 001 / 001-platform-foundation**: branding, i18n, JWT validation on the backend it calls
- **intent 001 / 004-collection-experience** (bolt 006): `/collection` and its filters — **not built**

#### Enables (other bolts waiting on this)

- 024-scan-experience

### Notes

**Development builds, not Expo Go.** Expo Go owns the `exp://` scheme and cannot exercise a
custom-scheme redirect, so sign-in cannot be tested in it. Set this up on day one.

**Verified, so do not re-investigate:** `login-api` matches `redirect_uri` by exact string membership
in a JSON allowlist with no scheme restriction (`authorization_service.py:74`), and the code exchange
takes no client secret (`token_service.py:84`). The mobile client is the same *kind* of client as the
web SPA. Register it, do not modify the platform.

**Android carries this bolt.** An APK installs on any device and needs no developer account. iOS needs
an Apple signing identity even for internal installs and none exists — so the iOS build is defined and
buildable, and **no acceptance criterion depends on it**.

**Pin the OTA channel to a native runtime version.** An unpinned channel eventually pushes JavaScript
expecting a native module an older binary lacks, and it appears as a launch crash for a subset of
testers with no obvious cause.
