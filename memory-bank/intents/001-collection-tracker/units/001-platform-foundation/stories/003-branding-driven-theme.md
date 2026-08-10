---
id: 003-branding-driven-theme
unit: 001-platform-foundation
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 001-platform-foundation
implemented: false
---

# Story: 003-branding-driven-theme

## User Story

**As a** platform operator
**I want** the app to follow the branding I configure
**So that** it looks like part of my product suite rather than a bolt-on

## Acceptance Criteria

- [ ] **Given** the app starts, **When** it initialises, **Then** it fetches the theme from branding-api's anonymous `/resolve` — sending no token
- [ ] **Given** a resolved brand exists, **When** the theme applies, **Then** chrome tokens (primary, surfaces, focus ring, link) follow it
- [ ] **Given** the brand changes, **When** I reload, **Then** the chrome changes and **element and rarity colours do not**
- [ ] **Given** branding-api is unreachable, **When** the app starts, **Then** the built-in default theme renders and nothing else degrades
- [ ] **Given** either theme is active, **When** contrast is measured, **Then** both light and dark satisfy WCAG 2.2 AA

## Technical Notes

- **The architectural point of this story**: two token layers. Chrome is tenant-derived; the eight element hues and the rarity materials are hard-coded domain constants in `theme/domain.ts`.
- Element colours are a data encoding. If a tenant could change them, the same hue would mean different things in different deployments.
- Uses `fetchBranding()` → `themeFromBranding()` from app-starter, applied over the whole app rather than only the login form.

## Dependencies

### Requires
- 002-app-shell-and-routing

### Enables
- Every visual story in the intent

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Brand sets a primary that fails contrast on our surfaces | Clamp lightness to reach AA and log a warning — never ship unreadable text |
| Brand returns a partial theme | Merge over the defaults per token, not all-or-nothing |
| Cache key unchanged after a manual reset | The platform advances the revision for exactly this case; honour it |

## Out of Scope

- Element and rarity palettes — deliberately not brandable
