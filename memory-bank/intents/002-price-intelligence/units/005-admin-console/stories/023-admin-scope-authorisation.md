---
id: 023-admin-scope-authorisation
unit: 005-admin-console
intent: 002-price-intelligence
status: complete
priority: must
created: '2026-08-15T15:00:00Z'
assigned_bolt: 013-admin-console-core
implemented: true
---

# Story: 023-admin-scope-authorisation

## User Story

**As the** owner of this system
**I want** every harvest surface to require the `elestrals:admin` scope
**So that** raw scraped data, and the ability to start a scraper, are available to exactly the
people who should have them and nobody else

## Acceptance Criteria

- [ ] **Given** a caller without `elestrals:admin`, **When** they call any `/api/v1/admin/*` route
      on `harvest-api`, **Then** they receive `403` with no body detail
- [ ] **Given** a caller without the scope, **When** they call an admin route, **Then** they never
      receive a `200` with the interesting fields filtered out
- [ ] **Given** any admin route, **When** it is defined, **Then** it uses the one shared dependency —
      verified by a test that enumerates the admin router and asserts every route carries it
- [ ] **Given** a request, **When** the scope is checked, **Then** it is read from the validated JWT
      and never from a body, query parameter or header
- [ ] **Given** a valid token with `elestrals:operator` but not `elestrals:admin`, **When** it calls
      an admin route, **Then** it is refused — the two roles are distinct
- [ ] **Given** local development, **When** `HARVEST_ADMIN_SUBS` lists a subject, **Then** that
      subject is treated as an admin, and this path is inert when `ENVIRONMENT=production`
- [ ] **Given** an expired or malformed token, **When** it is presented, **Then** the response is
      `401`, distinct from the `403` of a valid token without the scope

## Technical Notes

Mirrors the phase-1 `require_operator` dependency, including its recorded caveat that it is
provisional until the platform exposes real app roles. Two scopes, not one, deliberately: the person
who can re-import the catalog should not automatically be the person who can start a scraper
against a site that has asked us not to.

The route-enumeration test is the load-bearing one. Every other criterion protects a route that
exists today; that test protects the route somebody adds in six months.

`403` with no detail rather than a filtered `200`: a success-shaped response with fields removed
leaks the shape of what the caller cannot see, and trains the frontend to render an empty state that
actually means "forbidden".

**Open dependency**: whether the platform can issue `elestrals:admin` at all is unresolved (owner:
Lars, due before this unit). If it cannot, the fallback is the `sub` allowlist — which is a
development convenience, not an authorisation system, and shipping on it would be a decision worth
its own record.

## Dependencies

### Requires
- 001-harvest-service-skeleton
- intent 001 / 001-platform-foundation — JWT validation and the operator pattern this follows

### Enables
- Every other story in unit 005

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Platform cannot issue the scope | Fallback to the allowlist, and the gap is recorded. Not silently shipped as if equivalent |
| Token has the scope but the user was removed upstream | Token expiry bounds the window; we do not maintain a second user store to check against |
| A new admin route is added without the dependency | The enumeration test fails |
| `HARVEST_ADMIN_SUBS` is set in production | Ignored, and logged at `warning` at startup so the misconfiguration is visible |
| An admin route is called by the collection backend | There is no such call. The services do not call each other; only `price_daily` crosses |

## Out of Scope

- Per-admin permissions or an audit trail of who ran what — a single admin role for now
- Managing who is an admin. That is the platform's job
