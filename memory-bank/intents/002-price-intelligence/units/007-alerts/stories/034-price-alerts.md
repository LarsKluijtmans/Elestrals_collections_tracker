---
id: 034-price-alerts
unit: 007-alerts
intent: 002-price-intelligence
status: ready
priority: should
created: 2026-08-15T15:00:00Z
assigned_bolt: 017-alerts
implemented: false
---

# Story: 034-price-alerts

## User Story

**As a** collector
**I want** to be told when a card I care about crosses a price I chose
**So that** I can act on it without checking the site every day

## Acceptance Criteria

- [ ] **Given** a card page or a wishlist entry, **When** I set a threshold, **Then** an alert is
      created for that printing with a direction and a currency
- [ ] **Given** the rollup has finished for a day, **When** alerts are evaluated, **Then** those
      whose threshold was crossed are queued for delivery
- [ ] **Given** an alert has fired, **When** the price crosses again within the cooldown, **Then** it
      does not fire again
- [ ] **Given** an alert fires, **When** the message is composed, **Then** it states the price, the
      window and the confidence that triggered it
- [ ] **Given** a printing whose data is `low` confidence, **When** alerts are evaluated, **Then**
      nothing fires for it
- [ ] **Given** delivery, **When** it happens, **Then** it goes through the phase-1 outbox to
      notification-api, so an outage delays rather than loses
- [ ] **Given** an alert I no longer want, **When** I deactivate or delete it, **Then** it stops
      firing immediately

## Technical Notes

Evaluation runs as the **final step of the rollup job**, not on its own schedule. An alert evaluated
against a half-written day would fire on a partial median — and an alert is a claim that something
happened, so it has to be made on settled data.

The `low`-confidence rule matters more under ADR-004 than it would have under a licensed feed: more
of the data is thin, single-source or asking-price-derived, and firing on that would train users to
ignore alerts.

The message stating price, window and confidence is what makes an alert checkable. "Vipyro crossed
$20" cannot be acted on; "Vipyro's 7-day median crossed $20, from 6 sales across 2 sources" can.

## Dependencies

### Requires
- 016-daily-rollup-job — evaluation runs inside it
- 015-sold-vs-listed-separation — the confidence rule depends on it
- intent 001 / 007-profile-and-sharing — the outbox

### Enables
- Nothing. This is the last story in the intent

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Price oscillates around the threshold | Fires once per cooldown, default 24 hours |
| Alert set on a printing that later loses all data | Does not fire; the alert stays, dormant, and the UI can show it as having no data |
| A user with many alerts on one card | Each evaluated independently with its own cooldown |
| notification-api is down | Outbox retries; the alert is delayed, not lost |
| Threshold set in a currency with no rate that day | Not evaluated that day rather than evaluated at a stale rate |
| A user is deleted | Their alerts go with them |

## Out of Scope

- Alerts on sealed products — printings only, for now
- Portfolio-level movement alerts
- Any delivery channel other than the phase-1 outbox
