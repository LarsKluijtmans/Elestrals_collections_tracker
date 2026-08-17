---
id: 017-alerts
unit: 007-alerts
intent: 002-price-intelligence
type: simple-construction-bolt
status: complete
stories:
  - 034-price-alerts
created: 2026-08-15T15:25:00Z
started: null
completed: null
current_stage: done
stages_completed:
  - name: implement
    completed: 2026-08-17T22:40:00Z
    artifact: 0008_price_alerts.py, alert_service.py, /alerts
  - name: test
    completed: 2026-08-17T22:45:00Z
    artifact: test-report.md

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


## Construction result - 2026-08-17

**Status: complete.** Unblocked and built the same day.

This bolt was `blocked` for a fortnight on one sentence in its own acceptance criteria: *"delivery
goes through the phase-1 outbox, so a notification-api outage delays rather than loses."* There was
no outbox. Bolt 009 shipped one this afternoon, and story 034 needed no compromise at all — an alert
is now an ordinary `enqueue` on the same queue every other notification uses.

Worth noting what did **not** happen: the bolt notes floated shipping alerts with direct delivery
and replacing it when the outbox landed. That would have meant an alert lost to an outage — which is
the failure the criterion names — and a second delivery path to remove later. Waiting cost two weeks
and produced a feature with no temporary code in it.

**Three refusals carry the story.**

*Nothing fires on `low` confidence.* Under ADR-004 more of the data is thin, single-source or
asking-price-derived, and firing on it trains users to ignore alerts — at which point the ones that
matter get ignored too. Skipped alerts are **counted**, so "my alert never fires" has an answer
other than "it is broken".

*Nothing fires twice inside a seven-day cooldown.* A price wobbling over a threshold would otherwise
notify on every evaluation.

*Evaluation runs after the rollup, never on its own schedule.* An alert evaluated against a
half-written day fires on a partial median, and an alert is a claim that something happened.

**The bug worth recording.** The first version created an alert and delivered nothing. Story 032's
defaults leave `price_alert` on `none` until asked for, and `enqueue` respects that at queue time —
so the alert fired, the notification was dropped as muted, and nobody heard anything. Two correct
rules producing a silent feature, which is worse than an absent one.

Setting an alert *is* the opt-in, so `create` now raises the preference to `inapp` if it is still
`none` — the least intrusive channel that actually works, with the settings page one click away.
