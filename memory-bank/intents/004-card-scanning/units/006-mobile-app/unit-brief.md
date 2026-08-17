---
unit: 006-mobile-app
intent: 004-card-scanning
phase: inception
status: draft
created: '2026-08-17T13:25:00Z'
updated: '2026-08-17T13:25:00Z'
---

# Unit Brief: mobile-app

## Purpose

Build the client that does not exist.

This project has a React SPA and no mobile presence at all. This unit adds an Expo / React Native app
with three jobs: sign in against the platform, show the collection read-only, and reach a tester's
phone without an app store. The scanning itself is unit 007 — this unit builds the shell it renders
into.

The app is deliberately **narrow**. It is a scanner with a collection you can look at, not a second
copy of the product. Read-only is a load-bearing constraint, not a phase-one compromise: every editing
surface added here is a surface that must be built twice forever.

## Scope

### In Scope
- Expo app in `mobile/`, TypeScript strict, sharing Zod schemas and API types with the web app
- Authorization Code + PKCE against `login-api` on a **separate public client**, native redirect
  `elestrals://oauthredirect`, tokens in the platform keystore
- Read-only collection browse and search over the existing endpoints
- Read-only card detail and set completion, including price data where intent 002 has published it
- Offline availability of the last-viewed collection state
- CI-built Android artifact, internal distribution, OTA updates pinned to a native runtime version

### Out of Scope
- **Any editing.** No add, edit, delete, bulk action, saved view, import, export, settings or admin
  surface. Absent by construction, not hidden behind a flag
- The scan flow (unit 007)
- iOS release. The build is defined and buildable; shipping it is gated on a signing identity that
  does not exist, and **no requirement in this intent completes only on iOS**
- App Store or Play submission. Out of scope for the intent by decision
- Push notifications. The platform has `notification-api` and the app has no use for it yet

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-18 | The mobile app signs in against the platform | Must |
| FR-19 | The mobile app's read-only collection | Must |
| FR-20 | An internal release path for the mobile app | Must |

---

## Domain Concepts

### Key Entities

| Entity | Description | Attributes |
|--------|-------------|------------|
| MobileSession | The signed-in state on a device | `access_token`, `refresh_token`, `expires_at`, keystore-backed |
| AppRelease | What is running on a tester's phone | `native_runtime_version`, `js_bundle_version`, `build_number` |
| CachedCollection | The last-viewed collection, for offline | `fetched_at`, `items`, `etag` |

### Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `signIn()` | PKCE authorization code via the system browser | — | session |
| `refresh()` | Silent refresh, preserving any queued work | refresh token | session |
| `browse(filters)` | Read-only collection listing | filters | page |
| `cache.write(page)` | Persist for offline read | page | — |
| `reportVersion()` | Tell the backend what is running | release | — |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 6 |
| Must Have | 5 |
| Should Have | 1 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 027-expo-app-shell | An app that builds, themes and speaks two languages | Must | Planned |
| 028-native-pkce-sign-in | Sign in on a phone, holding no secret | Must | Planned |
| 029-mobile-collection-browse | Do I already own this? | Must | Planned |
| 030-mobile-card-detail-and-completion | The card, read-only, with its price if we have one | Must | Planned |
| 031-offline-collection-cache | A card shop with no signal is not a dead app | Should | Planned |
| 032-android-build-and-ota | On a tester's phone, without a store | Must | Planned |

---

## Dependencies

### Depends On

| Unit | Reason |
|------|--------|
| intent 001 / 001-platform-foundation | Branding, i18n conventions, JWT validation on the backend it calls |
| intent 001 / 004-collection-experience | The collection and completion endpoints it reads. **Note**: bolt 006 has not shipped, so `/collection` may not exist yet — see Constraints |

### Depended By

| Unit | Reason |
|------|--------|
| 007-scan-experience | The mobile half of the scan flow renders into this shell |

### External Dependencies

| System | Purpose | Risk |
|--------|---------|------|
| `login-api` client registration | The one thing outside this repository that must happen | **Low, and resolved** — verified to need a config row and no platform change |
| Expo / EAS | Build and OTA | Medium — a new toolchain in this project, with its own failure modes |
| Android device or emulator | Testing | Low |
| Apple signing identity | iOS builds | **Blocking for iOS only, by design.** Does not exist; no requirement depends on it |

---

## Technical Context

### Suggested Technology

Expo SDK with a **development build** rather than Expo Go — Expo Go owns the `exp://` scheme and
cannot exercise a custom-scheme redirect, so PKCE cannot be tested in it. `expo-auth-session` for the
flow, `expo-secure-store` for tokens, TanStack Query for server state (matching the web app so the
caching semantics are already understood), and no MUI.

Shared code with the web app is limited to what is genuinely platform-neutral: Zod schemas, API types,
and the on-device matcher from unit 003. Components are not shared, and pretending otherwise is how a
React Native codebase acquires a compatibility layer nobody wanted.

### Integration Points

| Integration | Type | Protocol |
|-------------|------|----------|
| `login-api` | outbound | OAuth2 PKCE, system browser |
| `elestrals-api` | outbound | HTTPS + platform JWT |
| `scan-api` | outbound | HTTPS + platform JWT (unit 007 uses it) |
| branding-api | outbound | HTTPS, anonymous resolve |

### Data Storage

| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| Tokens | platform keystore | tiny | until sign-out |
| Cached collection | on-device SQLite / MMKV | MBs | until refreshed |

---

## Constraints

- **No M2M secret ever reaches a device.** The app holds a public `client_id` and nothing else.
- **Tokens live in the keystore.** `AsyncStorage` is a plaintext file on a rooted device.
- **A failed refresh must not lose queued work.** Returning to sign-in with an unsent batch session
  discarded is the worst possible moment to lose a user's twenty scans.
- **No mobile-specific API variants.** The app reuses the endpoints the web app uses; a divergent
  mobile API is two APIs to keep correct.
- **Read-only by construction.** Not a hidden button, not a disabled state — the code is not there.
- **Android is the release target.** iOS builds must not gate this unit's completion.
- **`/collection` may not exist yet.** Intent 001's bolt 006 is unbuilt. If it has not shipped when
  this unit starts, stories 029 to 031 are blocked on it and that must be surfaced as a dependency
  rather than worked around with a bespoke mobile endpoint.
