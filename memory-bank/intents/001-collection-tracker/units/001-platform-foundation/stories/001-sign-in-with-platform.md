---
id: 001-sign-in-with-platform
unit: 001-platform-foundation
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 001-platform-foundation
implemented: false
---

# Story: 001-sign-in-with-platform

## User Story

**As a** collector
**I want** to sign in with my existing platform account
**So that** I do not create yet another password for yet another site

## Acceptance Criteria

- [ ] **Given** I am signed out, **When** I open any authenticated route, **Then** the embedded `<LoginForm>` renders in place of the page
- [ ] **Given** I complete sign-in, **When** I am redirected back, **Then** I land on the route I originally requested — not the dashboard
- [ ] **Given** my project enables only some sign-in methods, **When** the form renders, **Then** only those methods are offered
- [ ] **Given** I am signed in, **When** I inspect browser storage, **Then** the access token is not in `localStorage` or a JS-readable cookie
- [ ] **Given** I sign out, **When** the session clears, **Then** I return to the landing page and the token is gone from memory
- [ ] **Given** login-api is unreachable, **When** I try to sign in, **Then** I see a "sign-in unavailable" screen with a status link — not an indefinite spinner

## Technical Notes

- Authorization Code + PKCE only. This app never handles a credential and never sees a password.
- Reuse `app-starter`'s `security.py` verbatim: JWKS cache, `RS256` only, `iss` pinned, single-flight refresh.
- The frontend holds a public `client_id` and nothing else. Register the redirect URI and allowed origin on the project first or the flow is rejected server-side.

## Dependencies

### Requires
- None — first story

### Enables
- 002-app-shell-and-routing
- and every authenticated story in the intent

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Token expires mid-session | Silent refresh; the user notices nothing |
| Refresh token rejected | Fall back to the login gate with a message, preserving the current route |
| User signs out in another tab | This tab reconciles on next request rather than acting as signed in |
| Callback arrives with a mismatched `state` | Rejected as a CSRF attempt; no code exchange |

## Out of Scope

- Registration, password reset, MFA setup — all owned by the platform's own `/account`
