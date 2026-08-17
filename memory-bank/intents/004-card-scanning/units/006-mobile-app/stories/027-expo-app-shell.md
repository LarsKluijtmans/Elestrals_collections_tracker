---
id: 027-expo-app-shell
unit: 006-mobile-app
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:20:00Z'
assigned_bolt: 023-mobile-app-shell
implemented: false
---

# Story: 027-expo-app-shell

## User Story

**As** a collector
**I want** an actual app on my phone
**So that** scanning a shoebox is something I do with the device that has the camera, rather than
propping a laptop webcam against a stack of boxes

## Acceptance Criteria

- [ ] **Given** the repository, **When** the mobile app is built, **Then** it is an Expo project in
      `mobile/` with TypeScript in strict mode
- [ ] **Given** the app, **When** it makes API calls, **Then** it uses the **same Zod schemas** as the
      web app, shared as a package rather than duplicated
- [ ] **Given** the app, **When** it renders, **Then** its theme derives from the same resolved
      platform branding the web app uses — not a hardcoded palette
- [ ] **Given** the app, **When** language is set, **Then** EN and NL are available from the same
      translation sources as the web app
- [ ] **Given** the app, **When** an unhandled error occurs, **Then** an error boundary renders a usable
      screen rather than a white one
- [ ] **Given** the app, **When** MUI is searched for in its dependency tree, **Then** it is absent —
      the mobile UI is built, not ported
- [ ] **Given** the app, **When** it runs in Expo Go, **Then** this is understood to be unsupported: a
      **development build** is the supported path, because Expo Go cannot exercise the custom-scheme
      redirect story 028 needs

## Technical Notes

The shared surface with the web app is deliberately narrow: Zod schemas, API types, and (later) the
on-device matcher package from unit 003. Components are not shared. Attempting to share them produces a
compatibility layer that serves neither platform, and this project's tech stack already commits to
MUI on the web, which has no React Native equivalent worth pretending about.

TanStack Query on both sides, so caching, refetch and optimistic-update semantics are already
understood by anyone who has worked on the web app — that is a genuine reuse, unlike components.

The Expo Go caveat in the last criterion is worth stating up front rather than discovering: Expo Go
registers `exp://` and cannot be given `elestrals://`, so sign-in cannot be tested in it. Development
builds from day one.

## Dependencies

### Requires
- intent 001 / 001-platform-foundation — branding resolution, i18n conventions

### Enables
- 028-native-pkce-sign-in
- every other story in this unit and in unit 007's mobile half

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Branding resolution fails at launch | Fall back to a neutral default theme and continue. A branding outage must not be an app outage |
| The device language is neither EN nor NL | Fall back to EN, matching the web app |
| A shared Zod schema changes | Both clients see it at build time — which is the point of sharing it, and the reason to accept the packaging overhead |

## Out of Scope

- Authentication (story 028)
- Any collection data (stories 029–031)
- The scan flow (unit 007)
