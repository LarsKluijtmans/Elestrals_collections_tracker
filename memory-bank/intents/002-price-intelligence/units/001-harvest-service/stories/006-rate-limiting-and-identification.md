---
id: 006-rate-limiting-and-identification
unit: 001-harvest-service
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 010-harvest-service-foundation
implemented: false
---

# Story: 006-rate-limiting-and-identification

## User Story

**As the** person who carries the risk of this pipeline
**I want** every outbound request paced, bounded to an allowlisted host, and honestly identified
**So that** a site that objects can reach us before it blocks us, and so that the one part of our
conduct ADR-004 did **not** give up is enforced rather than intended

## Acceptance Criteria

- [ ] **Given** any outbound request, **When** it is made, **Then** it carries a User-Agent naming
      the product, its version and a contact address
- [ ] **Given** `HARVEST_CONTACT_EMAIL` is empty, **When** the harvester starts a scan, **Then** it
      refuses to run — an anonymous bot can only be blocked, never asked to slow down
- [ ] **Given** a source with `rate_limit_per_min = N`, **When** a scan runs, **Then** requests are
      paced continuously to N per minute rather than released in a burst on the minute
- [ ] **Given** a `429` with a `Retry-After`, **When** it is received, **Then** the delay the server
      named is used rather than our own schedule
- [ ] **Given** a `429` with no `Retry-After`, **When** it is received, **Then** backoff is
      exponential with jitter
- [ ] **Given** a response redirecting to another host, **When** it is received, **Then** it is
      refused rather than followed — a source that can return a link can otherwise steer us anywhere
- [ ] **Given** a host not on the outbound allowlist, **When** any code attempts a request to it,
      **Then** it is refused
- [ ] **Given** a rate limit change, **When** it is written to the source row, **Then** the next
      scan uses it, with no deploy

## Technical Notes

A token bucket per source, refilling **continuously** rather than in per-minute batches: a bucket
that refills on the minute lets a whole minute's budget leave at once and then stalls, which is the
traffic shape that gets a key throttled even when the average is legal.

The clock and the sleep function are injected so the pacing arithmetic is unit-testable without
actually waiting. A rate limiter tested by sleeping is a rate limiter tested once and then skipped.

Identity is stamped **per request**, last, so a caller cannot override it — and so that it survives
when an HTTP client is injected, which is every test and any future custom wiring.

`follow_redirects=False` throughout. An off-host redirect is exactly the case the allowlist exists
for; following it would launder the request through a check that already passed.

**Not in this story: robots.txt.** ADR-004 decided it is not consulted. That decision is recorded in
NFR §Conduct and in the ADR; this story implements everything that *was* kept.

## Dependencies

### Requires
- 004-source-registry-and-risk-gate

### Enables
- 007-source-connector-contract — every connector reaches the network through this
- 011-block-detection-and-quarantine — which watches the responses this layer receives

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| `Retry-After` is an HTTP-date rather than seconds | Falls through to our own exponential schedule rather than crashing on the parse |
| Source returns 403 immediately | Not retried — an answer, not a hiccup. Handed to story 011's block detection |
| Source returns 400/404 | Not retried; retrying a rejection spends someone else's capacity on a request that will fail identically |
| `rate_limit_per_min` set to 0 | Configuration error, raised at construction. Stopping a source is `enabled = 0`, not a zero rate |
| Two sources on the same host | Each has its own bucket, so the host sees the sum. Worth a note in the console; not solved here |

## Out of Scope

- robots.txt (deliberately — ADR-004)
- Proxy rotation, user-agent rotation, or anything else whose purpose is to avoid being recognised.
  ADR-004 kept identifiability on purpose, and these would give it up
- Detecting a block (story 011)
