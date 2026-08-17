---
id: 031-offline-collection-cache
unit: 006-mobile-app
intent: 004-card-scanning
status: ready
priority: should
created: '2026-08-17T14:24:00Z'
assigned_bolt: 023-mobile-app-shell
implemented: false
---

# Story: 031-offline-collection-cache

## User Story

**As** a collector in a shop with one bar of signal
**I want** the app to still know what I own
**So that** the place where I most need to check my collection is not the place where the app stops
working

## Acceptance Criteria

- [ ] **Given** a previously loaded collection, **When** the device has no network, **Then** the last
      viewed state is available and browsable
- [ ] **Given** cached data, **When** it is displayed, **Then** its staleness is **visible** — the user
      knows they are looking at a snapshot
- [ ] **Given** the network returning, **When** the app reconnects, **Then** the cache refreshes in the
      background without the user asking
- [ ] **Given** a cache, **When** it is written, **Then** it holds the collection summary needed to
      answer "do I own this", not the entire collection at full fidelity
- [ ] **Given** the cache, **When** the user signs out, **Then** it is cleared — a shared phone must not
      leak a previous user's collection

## Technical Notes

The question this cache exists to answer is narrow: *do I own this, and how many?* That is a compact
projection — printing id, quantity, condition — and it stays small even for a 10,000-card collection.
Caching full card detail for everything is a different and much larger problem that this story
deliberately does not solve.

TanStack Query's persistence with a bounded store, so the caching semantics match the web app rather
than being a bespoke second system.

Visible staleness is not optional. A collector making a purchase decision from a three-week-old
snapshot, with no indication it is old, is worse off than one who knows the app is offline.

## Dependencies

### Requires
- 029-mobile-collection-browse

### Enables
- 037-batch-scan-session — the offline add queue is a sibling mechanism and shares its persistence
  approach

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Cache is very old | Still shown, staleness prominent. Old data honestly labelled beats no data |
| The collection changed on the web while offline | Refresh on reconnect resolves it; the staleness indicator is what covers the gap in between |
| Device storage is full | Cache write fails gracefully; the app works online-only and says so |
| Two accounts used on one device | Cache is keyed by `user_sub` and cleared on sign-out, both |

## Out of Scope

- Offline card detail and price data
- Offline search across the whole catalog — the catalog index (story 011) is a separate artifact with
  a separate purpose
