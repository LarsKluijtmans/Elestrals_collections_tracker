---
id: 011-block-detection-and-quarantine
unit: 002-scrapers
intent: 002-price-intelligence
status: complete
priority: must
created: '2026-08-15T15:00:00Z'
assigned_bolt: 011-scraper-connectors
implemented: true
---

# Story: 011-block-detection-and-quarantine

## User Story

**As the** person who carries the risk of this pipeline
**I want** a source that has started refusing us to be left alone automatically
**So that** being blocked does not become being blocked harder, and so that the state is visible
rather than buried in a log

## Acceptance Criteria

- [ ] **Given** a source returning a sustained pattern of `403`, `429` or challenge responses,
      **When** the threshold is crossed, **Then** the source is quarantined and the current run ends
      `partial` with the reason
- [ ] **Given** a quarantined source, **When** any scan is scheduled or triggered for it, **Then**
      the gate refuses it for as long as the quarantine lasts
- [ ] **Given** a quarantine, **When** its backoff expires, **Then** exactly one probing request is
      made; if it succeeds the source resumes, if it fails the quarantine is re-applied with a
      longer backoff
- [ ] **Given** a quarantined source, **When** an admin looks at the console, **Then** it is visibly
      distinguished from a source that is merely finding nothing, and shows when it will be retried
- [ ] **Given** one source quarantined, **When** other sources run, **Then** they are unaffected
- [ ] **Given** any source state, **When** a user loads a price surface, **Then** the last published
      rollups still serve — a block degrades freshness, never availability
- [ ] **Given** an admin decides a source is not coming back, **When** they disable it, **Then** the
      kill switch takes effect on the next scan with no deploy

## Technical Notes

**This story exists only because of ADR-004.** Assertive scraping without a quarantine story means
the first block is met with retries, which is how a temporary block becomes a permanent one.

Quarantine is a **state of the source** (`quarantined_until` on `price_sources`), not a decision
each run makes. A run that hits a block does not merely give up; it records the state so the *next*
run does not repeat the attempt.

Detection is on a sustained pattern, not a single response: one `429` is normal traffic shaping and
story 006 already backs off for it. The threshold is per source and configurable, because sources
differ in how they signal.

Backoff is escalating — an hour, then several, then a day. The ceiling is configuration.

The single probing retry matters: resuming a full scan against a source that is still blocking
would re-trigger whatever caused it.

**What this story does not do:** make us harder to detect. ADR-004 kept identifiability
deliberately. Rotating user agents or addresses to evade a block would discard the one part of our
conduct the decision preserved, and would turn a contractual problem into a different kind.

## Dependencies

### Requires
- 006-rate-limiting-and-identification — this watches the responses that layer receives
- 004-source-registry-and-risk-gate — quarantine is a second reason the gate refuses

### Enables
- 026-run-history-and-health — quarantine state is one of the things it shows

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Source returns a challenge page with HTTP 200 | Counts as a block. The connector recognises its own source's challenge shape; the parser failing to find any expected field with a 200 is the general signal |
| Source blocks one query but not others | Threshold is over the run, not a single query — a narrow block should not quarantine a working source |
| Block is region-specific or transient | The probing retry finds out. This is exactly what it is for |
| All sources quarantined at once | Rollups keep serving; the console shows every source quarantined; ADR-004's review trigger "sustained quarantine of a majority of sources" is reached |
| An admin triggers a scan on a quarantined source | Refused, with when it will be retried and how to override by clearing the quarantine deliberately |

## Out of Scope

- Evasion of any kind — see the technical note
- Deciding to abandon a source permanently. FR-18 automates the backoff; the stop is a human call,
  and it is an open question owned by Lars
