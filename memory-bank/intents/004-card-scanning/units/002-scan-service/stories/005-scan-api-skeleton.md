---
id: 005-scan-api-skeleton
unit: 002-scan-service
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T13:40:00Z'
assigned_bolt: 019-scan-service-foundation
implemented: false
---

# Story: 005-scan-api-skeleton

## User Story

**As** a collector whose card identification is slow or failing
**I want** that failure to be contained in a service of its own
**So that** the collection I am signed in to look at stays up while the matcher does not

## Acceptance Criteria

- [ ] **Given** the repository, **When** `scan-api` is built, **Then** it is a separate FastAPI
      service in its own directory with its own `Dockerfile`, joining the existing
      `docker-compose.yml` and the existing release workflow as a third image
- [ ] **Given** the running stack, **When** `/health` is polled, **Then** `scan-api` answers
      independently of `elestrals-api` and `harvest-api`
- [ ] **Given** `scan-api` stopped, **When** any `/collection` request is made, **Then** it succeeds
      unchanged — verified by a test, not by inspection
- [ ] **Given** `scan-api` stopped, **When** a scan is attempted, **Then** the client falls back to the
      on-device pass, states that it did, and the add still completes
- [ ] **Given** a request, **When** it carries a platform JWT, **Then** `scan-api` validates it via
      JWKS with `RS256` and a pinned issuer, reusing the established `security.py` pattern rather than
      a second implementation
- [ ] **Given** any route, **When** it is served, **Then** it goes through the logged-route wrapper so
      requests land in the established logging path

## Technical Notes

Mirrors `harvest-api`'s structure deliberately, so all three services read alike:
`Controllers → Services → Repositories → SQLAlchemy models → MySQL`, `/api/v1` prefix, thin routers
with no DB access.

Port allocation follows the platform's convention; `9500` is the collection backend and the harvester
took the next. Whatever `scan-api` takes must be recorded in `tech-stack.md` alongside them, because
the ports table there is the only place the mapping is written down.

The isolation claim in the third and fourth criteria is the whole justification for this unit
existing. It is tested, not asserted — intent 002's FR-13 made the same claim and the same
requirement to prove it.

## Dependencies

### Requires
- intent 001 / 001-platform-foundation (JWT validation, logging conventions, the compose stack)

### Enables
- 006-scan-schema-and-grants
- everything else in this intent

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| `scan-api` is slow rather than down | Client-side ladder budget expires and returns the best candidate with `timed_out`; the collection backend is untouched either way |
| The service starts before MySQL | Health reports unhealthy; the container restarts per the compose policy, exactly as the other two services do |
| Someone adds a route without the logged wrapper | Caught in review; the wrapper is applied at router registration so forgetting it is a visible omission rather than a silent one |

## Out of Scope

- The schema and grants (story 006)
- Any domain logic at all — this story ships a service that does nothing, on purpose
