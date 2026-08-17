---
bolt: 017-alerts
stage: test
status: complete
created: 2026-08-17T22:45:00Z
---

# Test Report: 017-alerts

**Status: `complete`.** Every criterion met, and the one that blocked this bolt for a fortnight —
delivery through the phase-1 outbox — is met by *using* the outbox rather than by working around it.

## Automated

```
backend → pytest -q      571 passed   (was 542)
```

`test_portfolio_and_alerts.py` carries 15 alert tests alongside stories 021, 022 and 033, since all
four were unblocked by the same afternoon's phase-1 work and share fixtures.

## The three refusals

**`test_nothing_fires_on_low_confidence`.** Under ADR-004 more of the data is thin, single-source or
derived from asking prices. Firing on that trains people to ignore alerts, and once they do, the
ones that matter are ignored too. Skipped alerts are *counted* in the evaluation result rather than
silently dropped, so "my alert never fires" has an answer other than "it is broken".

**`test_an_alert_does_not_fire_twice_inside_the_cooldown`**, with
`test_it_fires_again_after_the_cooldown` for the other side. A price oscillating around a threshold
would otherwise notify on every evaluation — one notification about a crossing is information, six
is a reason to mute the channel.

**`test_deactivating_stops_it_firing_immediately`.** The evaluation only reads active rows, so there
is no window in which a switched-off alert can still go off.

## Delivery, and what the fortnight bought

`test_delivery_goes_through_the_outbox` asserts the alert is **queued**: `pending`, `sent_at` null.
That is story 034's sixth criterion and the reason this bolt sat `blocked` — *"an outage delays
rather than loses"* is an acceptance criterion, and there was nothing to delay in.

The bolt notes floated shipping with direct delivery and swapping it later. That would have meant an
alert lost to an outage — the exact failure the criterion names — plus a second delivery path to
remove afterwards. Waiting cost two weeks and produced a feature with no temporary code in it.

## The bug the tests caught

The first version created an alert and delivered **nothing**. Story 032's defaults leave
`price_alert` on `none` until the user asks, and `enqueue` respects that at queue time — so the
alert fired, the notification was dropped as muted, and no error appeared anywhere.

Two correct rules producing a silent feature, which is worse than an absent one: an absent feature is
obvious. Setting an alert *is* the opt-in, so `create` raises the preference to `inapp` when it is
still `none` — the least intrusive channel that actually works, with the settings page one click
away for anybody who wants mail instead.

## The message

`test_the_message_states_price_window_and_confidence` asserts the body carries the observation count,
the source count, the day and the confidence. Story 034's reasoning is worth repeating: *"Vipyro
crossed $20" cannot be acted on; "Vipyro's 7-day median crossed $20, from 6 sales across 2 sources"
can.* An alert that cannot be checked has to be taken on faith, and this product's whole claim is
that its numbers are checkable.

## Notes

`price_alerts` lives in `elestrals`, not the harvester's schema. That is FR-13 rather than
convenience: an alert is a user's row and `harvest-api` holds no grant on user data. The harvester
publishes `price_daily`; this service reads it, decides, and delivers.

`direction` is part of the unique key, so "below €20" and "above €40" on one card are two alerts —
both reasonable to want, and a single-threshold model could express neither properly.

Evaluation is also exposed as `POST /alerts/evaluate` so it can be run by hand while checking a
threshold — the same spirit as the harvester's manual rollup, and the same rule: the scheduled path
and the hand-run path are the same code.
