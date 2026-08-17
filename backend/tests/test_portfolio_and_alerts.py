"""Portfolio history, P/L, slice valuation and price alerts — stories 021, 022, 033 and 034.

All four were recorded `blocked` on phase-1 work that had not shipped. It has now, and these are
the tests for what that unblocked.

The assertions that carry the file are all refusals:

* a past day is valued with **that day's** prices, never today's
* a holding with no cost basis is **excluded and counted**, never assumed to have cost zero
* a day nothing priced gets **null**, and the chart breaks there rather than interpolating
* an alert **does not fire** on `low` confidence, and does not fire twice inside its cooldown
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.collection_snapshot import CollectionSnapshot
from app.models.price_daily import PriceDaily
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.price_repository import PriceRepository
from app.services.alert_service import AlertService, DuplicateAlert, InvalidAlert
from app.services.collection_filters import FilterSet
from app.services.notification_service import NotificationService
from app.services.portfolio_service import PortfolioService
from app.services.snapshot_service import SnapshotService
from app.services.valuation_service import ValuationService
from test_inventory import ALICE, BOB, build_service, seed_catalog

TODAY = date(2026, 8, 17)
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def catalog(db):
    return seed_catalog(db, card_count=4)


@pytest.fixture()
def inventory(db):
    return build_service(db)


@pytest.fixture()
def portfolio(db):
    return PortfolioService(InventoryRepository(db), PriceRepository(db))


@pytest.fixture()
def snapshots(db):
    return SnapshotService(db)


@pytest.fixture()
def alerts(db):
    return AlertService(
        db, PriceRepository(db), NotificationService(db, sender=lambda entry: None),
    )


def price(db, printing_id, *, day, cents, condition="", confidence="high",
          observations=8, sources=2, currency="EUR"):
    row = PriceDaily(
        id=str(uuid.uuid4()),
        printing_id=printing_id,
        sealed_product_id=None,
        excluded_count=0,
        product_key=printing_id,
        product_kind="printing",
        condition=condition or None,
        condition_key=condition,
        day=day,
        currency=currency,
        sale_type="sold",
        low_cents=cents, median_cents=cents, high_cents=cents, mean_cents=cents,
        observation_count=observations, source_count=sources,
        confidence=confidence,
        computed_at=datetime(2026, 8, 17, 3, 0),
    )
    db.add(row)
    db.commit()
    return row


# --- valuing a past day (story 022) ---------------------------------------------------

def test_a_past_snapshot_is_valued_with_that_days_prices(
    db, portfolio, snapshots, inventory, catalog,
):
    """**The assertion story 022 exists for.** Valuing history with today's rollups would make the
    whole chart move every night — the same failure as using today's FX rate for a year-old sale,
    which story 018 refuses for the same reason."""
    pid = catalog["printings"]["BS1-001:common"]
    inventory.add(ALICE, printing_id=pid)

    price(db, pid, day=date(2026, 3, 3), cents=1_000)
    price(db, pid, day=TODAY, cents=9_999)

    snapshots.take(taken_on=date(2026, 3, 3))
    (row,) = list(db.query(CollectionSnapshot))

    portfolio.value_snapshot(row, InventoryRepository(db).all_for_user(ALICE))
    db.commit()

    assert row.total_value_cents == 1_000     # March's price
    assert row.total_value_cents != 9_999     # not today's


def test_the_last_known_price_carries_forward(db, portfolio, snapshots, inventory, catalog):
    """Rollups exist only for days with observations. Carrying the last known price forward is
    what a price *is* between sales; the alternative is a chart that is mostly holes."""
    pid = catalog["printings"]["BS1-001:common"]
    inventory.add(ALICE, printing_id=pid)
    price(db, pid, day=date(2026, 3, 1), cents=1_500)

    snapshots.take(taken_on=date(2026, 3, 5))
    (row,) = list(db.query(CollectionSnapshot))
    portfolio.value_snapshot(row, InventoryRepository(db).all_for_user(ALICE))

    assert row.total_value_cents == 1_500


def test_a_day_nothing_priced_is_null_not_zero(db, portfolio, snapshots, inventory, catalog):
    """**Story 022's third criterion.** The chart breaks at that day rather than interpolating or
    drawing a zero. "We could not value this" is not "this was worth nothing"."""
    pid = catalog["printings"]["BS1-001:common"]
    inventory.add(ALICE, printing_id=pid)
    # A price exists, but only *after* the snapshot day.
    price(db, pid, day=date(2026, 12, 1), cents=1_000)

    snapshots.take(taken_on=date(2026, 3, 3))
    (row,) = list(db.query(CollectionSnapshot))
    portfolio.value_snapshot(row, InventoryRepository(db).all_for_user(ALICE))

    assert row.total_value_cents is None
    assert row.valuation_confidence == "none"


def test_an_empty_collection_is_genuinely_zero(db, portfolio, snapshots):
    """**Zero holdings is genuinely zero; unpriced holdings are not.** Story 022 says so, and
    conflating the two either erases legitimate zeros or invents values."""
    row = CollectionSnapshot(user_sub=ALICE, taken_on=TODAY, item_count=0, distinct_printings=0)
    db.add(row)
    db.commit()

    portfolio.value_snapshot(row, [])
    assert row.total_value_cents == 0


def test_valuing_is_re_runnable(db, portfolio, snapshots, inventory, catalog):
    """Story 022's fourth criterion. It reads `price_daily`, which is recomputed rather than
    accumulated, so a second run is the same arithmetic over the same inputs."""
    pid = catalog["printings"]["BS1-001:common"]
    inventory.add(ALICE, printing_id=pid, quantity=3)
    price(db, pid, day=TODAY, cents=1_000)

    snapshots.take(taken_on=TODAY)
    (row,) = list(db.query(CollectionSnapshot))
    holdings = InventoryRepository(db).all_for_user(ALICE)

    portfolio.value_snapshot(row, holdings)
    first = row.total_value_cents
    portfolio.value_snapshot(row, holdings)

    assert row.total_value_cents == first == 3_000


def test_the_backfill_walks_every_snapshot(db, portfolio, snapshots, inventory, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    inventory.add(ALICE, printing_id=pid)
    price(db, pid, day=date(2026, 3, 1), cents=1_000)

    for day in (date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 4)):
        snapshots.take(taken_on=day)

    valued, left_null = snapshots.value_days(portfolio, InventoryRepository(db))

    assert valued == 3
    assert left_null == 0


# --- P/L (story 021) ------------------------------------------------------------------

def test_a_holding_with_no_cost_basis_is_excluded_and_counted(
    db, portfolio, inventory, catalog,
):
    """**The refusal that keeps the number honest.** Assuming zero cost would report the entire
    market value as profit — wrong and flattering at once, which is the worst combination a
    financial figure can have."""
    with_cost = catalog["printings"]["BS1-001:common"]
    without = catalog["printings"]["BS1-002:common"]

    inventory.add(ALICE, printing_id=with_cost,
                  acquired_unit_price_cents=500, acquired_currency="EUR")
    inventory.add(ALICE, printing_id=without)

    price(db, with_cost, day=TODAY, cents=1_500)
    price(db, without, day=TODAY, cents=9_999)

    pnl = portfolio.profit_and_loss(InventoryRepository(db).all_for_user(ALICE))

    assert pnl.covered_items == 1
    assert pnl.uncovered_items == 1
    assert pnl.cost_cents == 500
    assert pnl.market_cents == 1_500          # not 1500 + 9999
    assert pnl.gain_cents == 1_000


def test_coverage_is_stated(db, portfolio, inventory, catalog):
    """Partial coverage is the *normal* case in phase 1, not an edge case — an unrealised gain
    over a third of a collection is a different claim from one over all of it."""
    for n, basis in ((1, 500), (2, None), (3, None)):
        inventory.add(
            ALICE, printing_id=catalog["printings"][f"BS1-{n:03d}:common"],
            acquired_unit_price_cents=basis,
            acquired_currency="EUR" if basis else None,
        )
        price(db, catalog["printings"][f"BS1-{n:03d}:common"], day=TODAY, cents=1_000)

    pnl = portfolio.profit_and_loss(InventoryRepository(db).all_for_user(ALICE))
    assert pnl.coverage == pytest.approx(1 / 3)


def test_a_cost_in_another_currency_is_excluded_not_converted(
    db, portfolio, inventory, catalog,
):
    """Converting here with an unspecified rate is exactly the invented precision story 018
    exists to prevent. Excluding it is honest; converting it silently is not."""
    pid = catalog["printings"]["BS1-001:common"]
    inventory.add(ALICE, printing_id=pid,
                  acquired_unit_price_cents=500, acquired_currency="USD")
    price(db, pid, day=TODAY, cents=1_500)

    pnl = portfolio.profit_and_loss(InventoryRepository(db).all_for_user(ALICE))
    assert pnl.covered_items == 0
    assert pnl.uncovered_items == 1


def test_a_loss_is_reported_as_a_loss(db, portfolio, inventory, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    inventory.add(ALICE, printing_id=pid,
                  acquired_unit_price_cents=2_000, acquired_currency="EUR")
    price(db, pid, day=TODAY, cents=800)

    pnl = portfolio.profit_and_loss(InventoryRepository(db).all_for_user(ALICE))
    assert pnl.gain_cents == -1_200


# --- performers (story 021) -----------------------------------------------------------

def test_performers_rank_by_contribution_not_unit_price(db, portfolio, inventory, catalog):
    """A common held forty times can outrank a single expensive holo — which is usually the
    interesting answer, and a different question from "my most valuable card"."""
    cheap = catalog["printings"]["BS1-001:common"]
    dear = catalog["printings"]["BS1-002:common"]

    inventory.add(ALICE, printing_id=cheap, quantity=40)
    inventory.add(ALICE, printing_id=dear, quantity=1)
    price(db, cheap, day=TODAY, cents=100)      # 40 × 100 = 4,000
    price(db, dear, day=TODAY, cents=3_000)     #  1 × 3000 = 3,000

    best, _ = portfolio.performers(InventoryRepository(db).all_for_user(ALICE))
    assert best[0].printing_id == cheap
    assert best[0].contribution_cents == 4_000


def test_unpriced_holdings_do_not_appear_as_performers(db, portfolio, inventory, catalog):
    inventory.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    best, worst = portfolio.performers(InventoryRepository(db).all_for_user(ALICE))
    assert best == []
    assert worst == []


# --- the slice (story 033) ------------------------------------------------------------

def test_a_slice_values_only_what_the_filter_matches(db, inventory, catalog):
    """Story 033, and it uses **`/collection`'s own filters** — two implementations over one data
    model disagree, and the disagreement reads as the valuation being broken."""
    damaged = catalog["printings"]["BS1-001:common"]
    mint = catalog["printings"]["BS1-002:common"]
    inventory.add(ALICE, printing_id=damaged, condition="damaged")
    inventory.add(ALICE, printing_id=mint, condition="mint")
    price(db, damaged, day=TODAY, cents=1_000)
    price(db, mint, day=TODAY, cents=5_000)

    items = InventoryRepository(db)
    valuation = ValuationService(PriceRepository(db))

    slice_holdings = items.browse(
        ALICE, FilterSet.from_params({"condition": ["damaged"]}),
        sort="added_desc", limit=1_000,
    )
    assert valuation.value(slice_holdings).total_cents == 1_000


def test_a_full_slice_equals_the_whole_portfolio(db, inventory, catalog):
    """**Worth its own test**, per story 033: a full-collection slice must equal `/portfolio` by
    construction rather than by coincidence."""
    for n in (1, 2, 3):
        pid = catalog["printings"][f"BS1-{n:03d}:common"]
        inventory.add(ALICE, printing_id=pid, quantity=n)
        price(db, pid, day=TODAY, cents=1_000)

    items = InventoryRepository(db)
    valuation = ValuationService(PriceRepository(db))

    whole = valuation.value(items.all_for_user(ALICE))
    sliced = valuation.value(
        items.browse(ALICE, FilterSet.from_params({}), sort="added_desc", limit=1_000)
    )
    assert sliced.total_cents == whole.total_cents


# --- alerts (story 034) ---------------------------------------------------------------

def test_creating_an_alert(alerts, catalog):
    alert = alerts.create(
        ALICE, printing_id=catalog["printings"]["BS1-001:common"],
        direction="below", threshold_cents=2_000,
    )
    assert alert.is_active is True


def test_two_alerts_in_the_same_direction_are_refused(alerts, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    alerts.create(ALICE, printing_id=pid, direction="below", threshold_cents=2_000)
    with pytest.raises(DuplicateAlert):
        alerts.create(ALICE, printing_id=pid, direction="below", threshold_cents=3_000)


def test_both_directions_on_one_card_are_allowed(alerts, catalog):
    """"Tell me when it goes below €20" and "tell me when it goes above €40" are two reasonable
    things to want about one card."""
    pid = catalog["printings"]["BS1-001:common"]
    alerts.create(ALICE, printing_id=pid, direction="below", threshold_cents=2_000)
    alerts.create(ALICE, printing_id=pid, direction="above", threshold_cents=4_000)
    assert len(alerts.list_for_user(ALICE)) == 2


def test_a_nonsense_threshold_is_refused(alerts, catalog):
    with pytest.raises(InvalidAlert):
        alerts.create(
            ALICE, printing_id=catalog["printings"]["BS1-001:common"],
            direction="below", threshold_cents=0,
        )


def test_an_alert_fires_when_the_threshold_is_crossed(db, alerts, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    alerts.create(ALICE, printing_id=pid, direction="below", threshold_cents=2_000)
    price(db, pid, day=TODAY, cents=1_500, confidence="high")

    result = alerts.evaluate(now=NOW)

    assert result.fired == 1
    inbox = NotificationService(db).for_user(ALICE)
    assert len(inbox) == 1
    assert "1,500" in inbox[0].body or "15.00" in inbox[0].body


def test_the_message_states_price_window_and_confidence(db, alerts, catalog):
    """**Story 034's fourth criterion.** "Vipyro crossed €20" cannot be acted on; "Vipyro's median
    is €15.00, from 6 sales across 2 sources on 17 August, confidence high" can — the reader can
    go and look at the same data."""
    pid = catalog["printings"]["BS1-001:common"]
    alerts.create(ALICE, printing_id=pid, direction="below", threshold_cents=2_000)
    price(db, pid, day=TODAY, cents=1_500, observations=6, sources=2, confidence="high")

    alerts.evaluate(now=NOW)
    body = NotificationService(db).for_user(ALICE)[0].body

    assert "6 sales" in body
    assert "2 sources" in body
    assert "high" in body
    assert TODAY.isoformat() in body


def test_nothing_fires_on_low_confidence(db, alerts, catalog):
    """**The refusal that keeps alerts worth reading.** Under ADR-004 more of the data is thin,
    single-source or asking-price-derived, and firing on that trains users to ignore alerts — at
    which point the ones that matter get ignored too."""
    pid = catalog["printings"]["BS1-001:common"]
    alerts.create(ALICE, printing_id=pid, direction="below", threshold_cents=2_000)
    price(db, pid, day=TODAY, cents=1_500, confidence="low")

    result = alerts.evaluate(now=NOW)

    assert result.fired == 0
    assert result.skipped_low_confidence == 1
    assert NotificationService(db).for_user(ALICE) == []


def test_an_alert_does_not_fire_twice_inside_the_cooldown(db, alerts, catalog):
    """A price oscillating around a threshold would otherwise notify on every evaluation. One is
    information; six is a reason to mute the channel."""
    pid = catalog["printings"]["BS1-001:common"]
    alerts.create(ALICE, printing_id=pid, direction="below", threshold_cents=2_000)
    price(db, pid, day=TODAY, cents=1_500)

    alerts.evaluate(now=NOW)
    second = alerts.evaluate(now=NOW + timedelta(hours=1))

    assert second.fired == 0
    assert second.in_cooldown == 1
    assert len(NotificationService(db).for_user(ALICE)) == 1


def test_it_fires_again_after_the_cooldown(db, alerts, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    alerts.create(ALICE, printing_id=pid, direction="below", threshold_cents=2_000)
    price(db, pid, day=TODAY, cents=1_500)

    alerts.evaluate(now=NOW)
    later = alerts.evaluate(now=NOW + timedelta(days=8))

    assert later.fired == 1


def test_an_above_alert_fires_on_the_other_side(db, alerts, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    alerts.create(ALICE, printing_id=pid, direction="above", threshold_cents=1_000)
    price(db, pid, day=TODAY, cents=1_500)

    assert alerts.evaluate(now=NOW).fired == 1


def test_an_uncrossed_threshold_does_not_fire(db, alerts, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    alerts.create(ALICE, printing_id=pid, direction="below", threshold_cents=1_000)
    price(db, pid, day=TODAY, cents=1_500)

    assert alerts.evaluate(now=NOW).fired == 0


def test_deactivating_stops_it_firing_immediately(db, alerts, catalog):
    """Story 034's last criterion. The evaluation only looks at active rows, so there is no window
    in which a switched-off alert can still go off."""
    pid = catalog["printings"]["BS1-001:common"]
    alert = alerts.create(ALICE, printing_id=pid, direction="below", threshold_cents=2_000)
    price(db, pid, day=TODAY, cents=1_500)

    alerts.set_active(ALICE, alert.id, active=False)

    assert alerts.evaluate(now=NOW).fired == 0


def test_delivery_goes_through_the_outbox(db, alerts, catalog):
    """**Story 034's sixth criterion, and what it was blocked on for a fortnight.** The alert is
    queued, not sent inline — so a notification-api outage delays it rather than losing it."""
    pid = catalog["printings"]["BS1-001:common"]
    alerts.create(ALICE, printing_id=pid, direction="below", threshold_cents=2_000)
    price(db, pid, day=TODAY, cents=1_500)

    alerts.evaluate(now=NOW)

    (entry,) = NotificationService(db).for_user(ALICE)
    assert entry.status == "pending"
    assert entry.event_type == "price_alert"
    assert entry.sent_at is None


def test_alerts_are_owner_scoped(alerts, catalog):
    alerts.create(
        ALICE, printing_id=catalog["printings"]["BS1-001:common"],
        direction="below", threshold_cents=2_000,
    )
    assert alerts.list_for_user(BOB) == []


def test_another_users_alert_is_a_404(alerts, catalog):
    from app.services.alert_service import AlertNotFound

    alert = alerts.create(
        ALICE, printing_id=catalog["printings"]["BS1-001:common"],
        direction="below", threshold_cents=2_000,
    )
    with pytest.raises(AlertNotFound):
        alerts.get(BOB, alert.id)
    with pytest.raises(AlertNotFound):
        alerts.delete(BOB, alert.id)
