---
id: 017-alerts
unit: 007-alerts
intent: 002-price-intelligence
type: simple-construction-bolt
status: blocked
stories:
  - 034-price-alerts
created: 2026-08-15T15:25:00Z
started: null
completed: null
current_stage: null
stages_completed: []

requires_bolts:
  - 014-rollups-and-valuation
  - 009-profile-and-sharing
enables_bolts: []
requires_units: []
blocks: false

complexity:
  avg_complexity: 1
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 2
---

# Bolt: 017-alerts

## Overview

Price thresholds on a printing, evaluated as the last step of the rollup job, delivered through the
phase-1 outbox.

## Objective

Let a collector be told when something moves, once, on data solid enough to act on.

## Stories Included

- **034-price-alerts**: fire once, on data worth acting on (Should)

## Bolt Type

**Type**: Simple Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/simple-construction-bolt.md`

A *simple* bolt on purpose: one table, one evaluation step appended to an existing job, and delivery
through an outbox phase 1 already built. There is no new domain modelling here — the confidence rule
it depends on was settled in bolt 014.

## Stages

- [ ] **1. implement**: Pending → `price_alerts` migration, evaluation in the rollup job, outbox
- [ ] **2. test**: Pending → test report

## Dependencies

### Requires
- 014-rollups-and-valuation (evaluation runs inside the rollup job)
- 009-profile-and-sharing (the outbox that delivery rides on)

### Enables
- Nothing. This is the last bolt in the intent

## Success Criteria

- [ ] An alert can be set from a card page or a wishlist entry, with direction and currency
- [ ] Evaluation runs as the **final step of the rollup job**, never on its own schedule
- [ ] An alert fires at most once per cooldown, default 24 hours
- [ ] Alerts **never** fire on `low` confidence data
- [ ] The message states the price, the window and the confidence that triggered it
- [ ] Delivery goes through the phase-1 outbox; a notification-api outage delays rather than loses
- [ ] Deactivating or deleting an alert stops it immediately
- [ ] Alerts are deleted with the user, like every other user-owned row
- [ ] Coverage > 80%

## Notes

Evaluating inside the rollup job rather than on its own schedule is the one design decision worth
protecting. An alert evaluated against a half-written day fires on a partial median — and an alert
is a claim that something happened, so it has to be made on settled data.

The `low`-confidence rule matters more under ADR-004 than it would have under a licensed feed: more
of the data is thin, single-source, or derived from asking prices. Firing on that trains users to
ignore alerts, which is worse than having none.

This is the smallest bolt in the intent and the right place to absorb schedule pressure — the story
is `Should`, and the product is complete without it.

## Construction result - 2026-08-15

**Status: blocked. Not started.**

Story 034 depends on the phase-1 **outbox** from intent 001 bolt 009 (`009-profile-and-sharing`),
which is still `planned`. Delivery "goes through the phase-1 outbox so an outage delays rather than
loses" is an acceptance criterion, not a preference, and there is no outbox to go through.

It also depends on the wishlist (bolt 007, also `planned`) for one of its two entry points.

Building a direct notification-api call to fill the gap was considered and rejected: it would have
to be replaced the moment the outbox lands, and in the meantime an alert lost to an outage is an
alert that silently did not fire - the failure this story's acceptance criteria are written to
prevent.

**Unblocks when:** intent 001 bolt 009 ships.
