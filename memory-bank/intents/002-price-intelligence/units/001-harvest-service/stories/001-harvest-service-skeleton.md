---
id: 001-harvest-service-skeleton
unit: 001-harvest-service
intent: 002-price-intelligence
status: complete
priority: must
created: '2026-08-15T15:00:00Z'
assigned_bolt: 010-harvest-service-foundation
implemented: true
---

# Story: 001-harvest-service-skeleton

## User Story

**As an** operator
**I want** the harvester to be its own deployable service
**So that** a scraper being blocked, breaking or being rewritten cannot take down the collection
tracker people are signed into

## Acceptance Criteria

- [ ] **Given** the compose stack, **When** I bring it up, **Then** `harvest-api` starts as its own
      container alongside `elestrals-api`, with its own port and its own health endpoint
- [ ] **Given** `harvest-api` is stopped, **When** a user loads `/collection`, **Then** the page
      works exactly as before, with no error and no degraded response time
- [ ] **Given** `harvest-api` is stopped, **When** a user loads a price surface, **Then** it serves
      the last published rollups and says when they were last updated — it does not error
- [ ] **Given** the release workflow, **When** a release is cut, **Then** both images are built,
      tagged with the same version, and published
- [ ] **Given** the service, **When** it starts, **Then** it reads its own `.env` keys and fails
      loudly on a missing required one rather than starting half-configured
- [ ] **Given** a `GET /health`, **When** called, **Then** it reports the service, its version, and
      whether it can reach MySQL and Redis — each separately, so a partial outage is legible

## Technical Notes

A sibling directory `harvest/`, structured like `backend/` so the two read alike: `app/` with
`controllers/`, `services/`, `repositories/`, `models/`, its own `config.py`, its own `Dockerfile`.
Shared *conventions*, not shared code — a common package between two services is a coupling that
will be regretted the first time one needs to change a convention.

The two services are peers in the compose project. `harvest-api` does not sit behind
`elestrals-api`, and `elestrals-api` never calls it: the only thing that crosses between them is a
read on `price_daily` (story 019).

Config keys are prefixed `HARVEST_*` and live in the same `.env`, so a single deployment configures
both without two files drifting.

## Dependencies

### Requires
- intent 001 / 001-platform-foundation — the compose stack and the release workflow this joins

### Enables
- 002-harvest-schema-and-grants
- Everything else in the intent

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| `harvest-api` cannot reach MySQL at startup | Starts, health reports the DB as down, scans refuse to run rather than crash-looping |
| `harvest-api` cannot reach Redis | Same: health says so, scheduled work does not run, the API still answers |
| Both services deployed at different versions | Allowed. The only contract is `price_daily`, and it is versioned by being additive-only |
| Someone adds a shared Python package between the services | Review failure. Convention is shared; code is not |

## Out of Scope

- Any connector, scan or schema (later stories)
- Splitting the frontend — the SPA stays one app with an admin section
