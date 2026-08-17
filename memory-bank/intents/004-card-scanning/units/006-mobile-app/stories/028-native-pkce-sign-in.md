---
id: 028-native-pkce-sign-in
unit: 006-mobile-app
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T14:21:00Z'
assigned_bolt: 023-mobile-app-shell
implemented: false
---

# Story: 028-native-pkce-sign-in

## User Story

**As** a collector
**I want** to sign in on my phone with the same account I use on the website
**So that** the cards I scan land in the collection I already have — and without the app holding any
credential that could be extracted from it

## Acceptance Criteria

- [ ] **Given** `login-api`, **When** the mobile client is registered, **Then** it is a **separate
      public client** from the web SPA, so revoking one does not affect the other
- [ ] **Given** the registration, **When** its redirect allowlist is set, **Then** it contains exactly
      `elestrals://oauthredirect`
- [ ] **Given** the registration, **When** grant types are set, **Then** they are `authorization_code`
      and `refresh_token`, and **not** `client_credentials`
- [ ] **Given** a sign-in, **When** the authorization request is made, **Then** it sends
      `code_challenge_method=S256`, which `login-api` requires
- [ ] **Given** the redirect, **When** it is sent at `/authorize` and again at `/token`, **Then** it is
      byte-identical to the registered string — it is validated in both places
- [ ] **Given** tokens, **When** they are stored, **Then** they are in the platform keystore (Keychain /
      Keystore) and **never** in `AsyncStorage`
- [ ] **Given** an expiring token, **When** refresh runs, **Then** it is silent and does not interrupt
      the user
- [ ] **Given** a failed refresh, **When** the user is returned to sign-in, **Then** any queued batch
      session survives and is not discarded
- [ ] **Given** the app bundle, **When** it is inspected, **Then** it contains a public `client_id` and
      **no** M2M secret

## Technical Notes

**Verified against the platform source rather than assumed** — this story needs no change to
`login-api`:

- `authorization_service.py:74` — `if redirect_uri not in client.redirect_uris`. Exact string
  membership against a JSON allowlist. **No scheme validation**, so a custom scheme is accepted
- `token_service.py:84` — `exchange_authorization_code(code, code_verifier, redirect_uri, client_id)`.
  **No `client_secret` parameter.** Only `issue_client_credentials` requires one
  (`token_service.py:205`)
- `authorization_service.py:76` and `token_service.py:118` — `S256` is mandatory at both ends

So the mobile client is the same *kind* of client the web SPA already is, and this story's external
dependency is a config row created through the platform's management console. No `elestrals` string
appears anywhere in the `auth` repository, confirming client registration is a runtime action —
consistent with `VITE_LOGIN_CLIENT_ID` being supplied by environment on the web side.

Implementation: `expo-auth-session` for the flow through the system browser (never an embedded
webview, which defeats the point of using the system browser's session), `expo-secure-store` for
tokens. `app.json` sets `"scheme": "elestrals"`, and `makeRedirectUri({ scheme: 'elestrals', path:
'oauthredirect' })` produces the registered string.

The queued-session criterion is not a nicety. A refresh failing after twenty scans, discarding them,
is the worst possible moment to lose a user's work.

## Dependencies

### Requires
- 027-expo-app-shell
- **External**: the `login-api` client registration (resolved 2026-08-17 — the value is known and no
  platform change is needed)

### Enables
- 029-mobile-collection-browse
- every authenticated call the app makes

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Another Android app registers the same custom scheme | A real weakness of custom schemes. Mitigated by PKCE — an intercepted code is useless without the verifier. App Links are the stronger fix and need domain hosting, so they are a later upgrade, recorded here rather than forgotten |
| The user cancels in the system browser | Returns to a signed-out state cleanly, with no half-open session |
| The redirect string differs by one character | `invalid_redirect_uri` from `login-api`. Worth knowing the error, because it is the most likely first-day failure |
| Refresh token revoked server-side | Sign-in again; queued work preserved |
| The device clock is badly wrong | JWT validation fails with a confusing error; detect skew and say so rather than reporting a generic auth failure |

## Out of Scope

- iOS universal links — the stronger redirect mechanism, deferred with iOS itself
- Biometric re-auth
