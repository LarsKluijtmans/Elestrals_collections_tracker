---
unit: 007-alerts
intent: 002-price-intelligence
phase: inception
status: ready
created: '2026-08-15T14:55:00Z'
updated: '2026-08-15T14:55:00Z'
---

# Unit Brief: alerts

## Purpose

Tell a collector when something they care about crosses a threshold — once, with a cooldown, and
only on data solid enough to act on.

Split out of the old `alerts-and-ops` unit, which was pairing this with the operations console for
no reason beyond both being "the leftovers". They share nothing: one is a scheduled evaluation
against rollups, the other is a whole admin surface.

## Scope

### In Scope
- A threshold on a printing, set from the card page or a wishlist entry
- Evaluation inside the rollup job, so an alert cannot fire on a number that has not settled
- Cooldown per alert
- Delivery through the phase-1 outbox to notification-api
- The alert message stating the price, the window and the confidence that triggered it

### Out of Scope
- Alerts on sealed products — printings only, for now
- Alerts on portfolio-level movement
- Any new delivery channel; the phase-1 outbox is the only path out

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-11 | Price alerts | Should |

---

## Domain Concepts

### Key Entities
| Entity | Description | Attributes |
|--------|-------------|------------|
| PriceAlert | One user's threshold on one printing | `user_sub`, `printing_id`, `direction`, `threshold_cents`, `currency`, `is_active`, `last_fired_at`, `cooldown_hours` |

### Key Operations
| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `evaluate(day)` | After the rollup, which alerts crossed? | day's `price_daily` | alerts to fire |
| `fire(alert)` | Enqueue delivery, stamp the cooldown | alert, triggering figure | outbox entry |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 1 |
| Must Have | 0 |
| Should Have | 1 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 034-price-alerts | Fire once, on data worth acting on | Should | Planned |

---

## Dependencies

### Depends On
| Unit | Reason |
|------|--------|
| 004-rollups-and-valuation | Alerts evaluate against `price_daily`, inside the rollup job |
| intent 001 / 007-profile-and-sharing | The outbox that delivery rides on |

### Depended By
| Unit | Reason |
|------|--------|
| — | Nothing. This is a leaf, and the last thing in the intent |

### External Dependencies
| System | Purpose | Risk |
|--------|---------|------|
| notification-api | delivery | Low — via the phase-1 outbox, so an outage delays rather than loses |

---

## Technical Context

### Suggested Technology
Evaluation runs as the final step of the rollup job rather than as its own schedule, so an alert
cannot fire against a half-written day. Delivery is an outbox row, drained by the phase-1 worker.
Alerts live in `elestrals` (they belong to a user), which means evaluation reads `price_daily`
cross-schema exactly as valuation does.

### Integration Points
| Integration | Type | Protocol |
|-------------|------|----------|
| notification-api | outbound | via the phase-1 outbox |
| `elestrals_harvest.price_daily` | inbound read | MySQL cross-schema, read-only |

### Data Storage
| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| `price_alerts` | SQL | a few per active user | until deleted by the user |

---

## Constraints

- **Never fire on `low` confidence data.** An alert is a claim that something happened; firing on a
  single scraped asking price makes that claim falsely, and under ADR-004 more of the data is
  `low`-confidence than it would have been under a licensed feed.
- **At most once per cooldown window**, default 24 hours. A price oscillating around a threshold
  must not produce a notification storm.
- **The message states what triggered it** — the price, the window, and the confidence. An alert
  that just says "Vipyro crossed $20" cannot be acted on or checked.
- Alerts belong to the user and are deleted with them, like every other user-owned row in phase 1.
