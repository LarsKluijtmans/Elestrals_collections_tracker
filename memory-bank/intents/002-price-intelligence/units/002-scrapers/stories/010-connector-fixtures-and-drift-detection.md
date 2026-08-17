---
id: 010-connector-fixtures-and-drift-detection
unit: 002-scrapers
intent: 002-price-intelligence
status: complete
priority: must
created: '2026-08-15T15:00:00Z'
assigned_bolt: 011-scraper-connectors
implemented: true
---

# Story: 010-connector-fixtures-and-drift-detection

## User Story

**As a** developer
**I want** each connector tested against a recorded response, and a test that fails when a source
changes its structure
**So that** a broken scraper announces itself instead of quietly returning nothing

## Acceptance Criteria

- [ ] **Given** each connector, **When** its tests run, **Then** they run against committed recorded
      responses and make no network call
- [ ] **Given** a recorded response, **When** the connector parses it, **Then** every field the
      contract promises is asserted — id, title, url, price, currency, and the sold flag where the
      source reports one
- [ ] **Given** a drift check, **When** it runs against the live source, **Then** it fetches one
      known query and **fails** if the structure no longer yields the fields the fixture does
- [ ] **Given** the drift check fails, **When** it reports, **Then** it names which field stopped
      being found, not merely that the count was zero
- [ ] **Given** the drift check, **When** CI runs, **Then** it is **not** part of the normal suite —
      it runs on a schedule, because a third party being down must not fail a pull request
- [ ] **Given** a source returning zero results legitimately, **When** the drift check runs, **Then**
      it distinguishes "parsed fine, nothing matched" from "could not parse"

## Technical Notes

The last criterion is the whole point of the story. Under ADR-004 a connector will break — sites
change markup without notice — and the failure mode is *silence*: zero rows looks exactly like a
quiet market. Every mitigation in this intent for that failure is here or in story 028's accept-rate
trend.

Fixtures are recorded responses committed to the repo. They go stale, and that is fine: a stale
fixture tests that our parser still parses what we recorded, and the scheduled drift check is what
tests that the recording still resembles reality.

Fixture hygiene: strip anything that is not needed to exercise the parser. We record structure, not
someone's listing history, and never anything that identifies a seller or a buyer.

## Dependencies

### Requires
- 007-source-connector-contract

### Enables
- 011-block-detection-and-quarantine — the two together are how an assertive scraper stays honest
- 028-coverage-and-match-quality

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Source is temporarily down when the drift check runs | Reported as unreachable, not as drift. Different problem, different alert |
| Source A/B-tests two markups | Drift check flaps. Record both fixtures and accept either |
| A field becomes optional upstream | Drift check fails; a human decides whether the connector should tolerate its absence. Not automatic |
| Fixture is huge | Trim to the smallest response that exercises every parsed field |
| Source starts returning a challenge page | That is a block, not drift — story 011 owns it |

## Out of Scope

- Detecting blocks (story 011)
- Automatically repairing a connector against a changed source
