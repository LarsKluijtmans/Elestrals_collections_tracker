---
id: 032-android-build-and-ota
unit: 006-mobile-app
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:25:00Z'
assigned_bolt: 023-mobile-app-shell
implemented: false
---

# Story: 032-android-build-and-ota

## User Story

**As** the person testing this
**I want** the app on a real phone without an app store
**So that** the intent can complete without depending on developer accounts that do not exist and a
trademark question that has not been answered

## Acceptance Criteria

- [ ] **Given** the repository, **When** CI runs, **Then** it produces an installable **Android**
      artifact — from CI, not from a laptop
- [ ] **Given** that artifact, **When** a tester installs it, **Then** it runs with **no developer
      account of any kind** required
- [ ] **Given** a JavaScript-only change, **When** it is released, **Then** it ships over the air
      without a new binary
- [ ] **Given** an OTA update, **When** it is published, **Then** it is **pinned to a native runtime
      version**, so an update cannot land on an incompatible binary
- [ ] **Given** the running app, **When** it calls the backend, **Then** it reports its version and
      build, so a bug report identifies what was running
- [ ] **Given** the iOS build, **When** it is defined, **Then** it is buildable and **explicitly gated**
      on an Apple signing identity — and **no acceptance criterion in this intent depends on it**
- [ ] **Given** the release path, **When** it is documented, **Then** it sits alongside the platform's
      existing compose-based deployment documentation rather than in a separate place

## Technical Notes

Android carries this intent. An APK installs on any device with unknown sources enabled and costs
nothing. iOS requires a signing identity even for internal device installs — free provisioning gives
seven-day builds, a paid account gives TestFlight — and **neither exists**. That asymmetry was
discovered while answering the redirect-URI question and is recorded here so it is not re-learned
during a bolt.

The runtime-version pin on OTA is the criterion most likely to be skipped and most likely to cause a
confusing outage. An OTA channel that is not pinned will eventually push JavaScript expecting a native
module that an older binary does not have, and the failure appears as a crash on launch for a subset
of testers with no obvious cause.

Version reporting to the backend costs almost nothing and is the difference between "the scanner is
broken" and "the scanner is broken on build 47".

## Dependencies

### Requires
- 027-expo-app-shell

### Enables
- Any testing of unit 007 on a real device

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A tester's device blocks unknown sources | Documented workaround; this is a normal Android setting, not a product defect |
| An OTA update breaks the app | Rollback to the previous OTA bundle, which is why bundles are retained rather than replaced |
| Someone asks for a store listing | Out of scope by decision. It needs developer accounts and a trademark answer, and belongs to a future intent |
| The native runtime changes | New binary, new build distributed to testers. OTA cannot cross that boundary and must refuse to |
| CI secrets for signing | Android debug/internal signing keys in CI secrets; documented alongside the platform's existing deployment secrets |

## Out of Scope

- App Store and Play submission
- iOS release
- Trademark permission for any store listing
