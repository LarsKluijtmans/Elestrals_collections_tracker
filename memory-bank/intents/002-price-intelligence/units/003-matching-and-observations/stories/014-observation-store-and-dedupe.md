---
id: 014-observation-store-and-dedupe
unit: 003-matching-and-observations
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 012-matching-and-observations
implemented: false
---

# Story: 014-observation-store-and-dedupe

## User Story

**As an** admin
**I want** re-running a scan to be free and safe
**So that** I can run the scrapers as often as I like without inflating the data they produce

## Acceptance Criteria

- [ ] **Given** a matched listing above the floor, **When** it is recorded, **Then** one
      `price_observations` row is written with source, run, SKU, condition, sale type, observed
      time, price, currency, external id, source URL and match confidence
- [ ] **Given** the same scan re-run within the same day, **When** it records, **Then** no duplicate
      observation is written and the run reports 0 accepted
- [ ] **Given** a listing whose price changed since yesterday, **When** today's scan records it,
      **Then** a new row is written for today
- [ ] **Given** a completed sale, **When** it is recorded, **Then** it keys on the source's own
      transaction id, so the same sale is never counted twice however often it is seen
- [ ] **Given** a match below the confidence floor, **When** it is processed, **Then** no observation
      is written and the run counts it as rejected
- [ ] **Given** any observation, **When** it is read back, **Then** `source_url` leads to a page a
      human can open
- [ ] **Given** an existing observation, **When** anything tries to update it, **Then** the store
      refuses — the table is append-only

## Technical Notes

`UNIQUE (source_id, external_id)` is the whole idempotency story, and the external id is built
differently by sale type:

| Sale type | External id | Why |
|---|---|---|
| `sold` | the source's transaction id | A sale happens once |
| `listed` | `{listing_id}@{YYYY-MM-DD}` | The same offer is seen on every scan, at a price that may move. One asking-price point per listing per day: an hourly light scan writes one row a day, and tomorrow's change still lands as its own point |

Insert-or-**ignore**, not upsert. Hitting the constraint means we already have this fact, and the
right response is to do nothing. Updating instead would let a second look rewrite the price recorded
the first time, which is how a fact table quietly becomes a cache.

The primary key is a `BIGINT AUTO_INCREMENT` against the project rule that public ids are UUIDs,
because at the 50M-row NFR target a random 36-character key is a page-split machine. It is legal
here precisely because this id never leaves the backend — the API exposes rollups and, at most, a
`source_url`.

Under ADR-004 the `source_url` requirement matters more, not less. Scraped data that cannot be
traced back to a page a human can open is not evidence of anything.

## Dependencies

### Requires
- 012-title-to-printing-matcher
- 013-condition-extraction

### Enables
- 015-sold-vs-listed-separation
- 016-daily-rollup-job
- 025-listing-explorer, 029-price-distribution-and-source-agreement

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Two runs write the same observation concurrently | The constraint resolves it; one insert wins, the other is ignored. No lock, no read-then-write |
| A price is later found to be wrong | A new row plus an exclusion flag. Never an edit — a history that can be silently rewritten is not evidence |
| Clock differences between source and us | `observed_at` is when the sale happened or the price was being asked, never when we read it. A backfill stamping its own clock flattens a year of history onto one afternoon |
| Source id changes format | The dedupe key changes with it; the old rows stay, the new ones are new facts. Visible as a discontinuity in the explorer, which is honest |
| An observation with no matched SKU | Impossible by construction — nothing under the floor is written |

## Out of Scope

- Aggregating them (story 016)
- Deleting or correcting rows through any interface
