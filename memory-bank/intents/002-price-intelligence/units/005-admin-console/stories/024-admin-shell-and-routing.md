---
id: 024-admin-shell-and-routing
unit: 005-admin-console
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 013-admin-console-core
implemented: false
---

# Story: 024-admin-shell-and-routing

## User Story

**As an** admin
**I want** a section of the app that is mine
**So that** the harvest tools have somewhere to live, and a non-admin never sees or downloads them

## Acceptance Criteria

- [ ] **Given** an admin, **When** they sign in, **Then** an admin entry appears in the navigation
      and `/admin/harvest` is reachable
- [ ] **Given** a non-admin, **When** they sign in, **Then** no admin entry appears and
      `/admin/harvest` renders the app's standard not-found rather than a "forbidden" page
- [ ] **Given** a non-admin, **When** they load the app, **Then** the admin bundle is **not
      downloaded** — verified by inspecting the network requests, not by the UI being hidden
- [ ] **Given** an admin, **When** they navigate within the admin section, **Then** the shell
      persists and only the panel changes
- [ ] **Given** the admin section, **When** it renders, **Then** it uses the phase-1 theme and
      branding tokens, not a separate visual language
- [ ] **Given** `harvest-api` is unreachable, **When** an admin loads the section, **Then** it shows
      a clear "harvest service unavailable" state rather than an empty console that looks like no
      data

## Technical Notes

A lazy-loaded route bundle, with the scope checked before the chunk is requested. Hiding an admin
section client-side leaves the code and the routes in the bundle for anyone who opens a network tab
— which is not a breach on its own, but it publishes the shape of the admin surface and every
endpoint path it calls.

Not-found rather than forbidden for a non-admin route: consistent with the phase-1 standard that an
unauthorised access to a real resource returns 404 rather than confirming it exists.

The admin section talks to `harvest-api` directly, on its own base URL, with the same platform
bearer token. It does not proxy through `elestrals-api` — a proxy would make the collection backend
a dependency of the admin console and undo half of FR-13.

## Dependencies

### Requires
- 023-admin-scope-authorisation
- intent 001 / 001-platform-foundation — the app shell, theme and routing this mounts into

### Enables
- 025-listing-explorer, 026-run-history-and-health, 027-trigger-and-watch-a-scan
- 028, 029

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Token gains the scope mid-session | The entry appears on the next token refresh; no forced reload |
| Token loses the scope mid-session | Admin calls start returning `403`; the section shows a signed-out-of-admin state rather than a broken page |
| CORS between the SPA and `harvest-api` | `harvest-api` allows the SPA origin explicitly, same pattern as phase 1 |
| Deep link to an admin route while signed out | Sign-in first, then the route, as everywhere else in the app |

## Out of Scope

- A separate admin application. One SPA, one theme, one deployment
- Any admin surface for the phase-1 catalog console, which stays where it is
