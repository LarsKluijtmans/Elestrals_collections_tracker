---
id: 002-app-shell-and-routing
unit: 001-platform-foundation
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 001-platform-foundation
implemented: false
---

# Story: 002-app-shell-and-routing

## User Story

**As a** collector
**I want** consistent navigation and a language I read
**So that** I can move around without relearning the layout on every page

## Acceptance Criteria

- [ ] **Given** I am on a wide screen, **When** the shell renders, **Then** a 240px left rail shows the phase-1 destinations
- [ ] **Given** the viewport drops below 1280px, **When** it reflows, **Then** the rail collapses to a 64px icon rail; below 900px it becomes a bottom tab bar
- [ ] **Given** I switch language, **When** the page re-renders, **Then** EN/NL applies across the app and the login UI, and persists to `localStorage`
- [ ] **Given** a component throws, **When** the error boundary catches it, **Then** I see a recoverable error page — never a blank screen
- [ ] **Given** I paste a deep link while signed out, **When** I sign in, **Then** I land on that page
- [ ] **Given** any page renders, **When** inspected, **Then** it has a unique `<title>` and exactly one `h1`

## Technical Notes

- One shared i18next instance, merging the login UI's `login` namespace — two instances means two翻译 sources drifting apart.
- Routing structure mirrors the page inventory in `standards/ux-guide.md` §11.

## Dependencies

### Requires
- 001-sign-in-with-platform

### Enables
- Every page in the intent

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Unknown route | A 404 page inside the shell, with navigation still available |
| Language file missing a key | Falls back to EN rather than rendering the raw key |
| Deep link to a route the user cannot access | 404, not 403 — we do not confirm what exists |

## Out of Scope

- Page content — each page is its own story
