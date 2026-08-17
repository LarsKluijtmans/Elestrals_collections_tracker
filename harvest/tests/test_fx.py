"""FX normalisation — story 018.

The assertion the story exists for is `test_a_past_amount_uses_that_days_rate`. Using today's rate
for a year-old sale rewrites history every morning: the same past day's value moves because the euro
moved, and a portfolio chart then shows movement that never happened.

Worth noticing that story 022 arrived at the identical rule independently, for valuing a past
snapshot with that day's rollups. Two stories, one principle: **a figure about a past day is
computed from that day's inputs.**
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.fx_rate import FxRate
from app.services.fx_service import MAX_CARRY_FORWARD_DAYS, FxService, NoRateAvailable

DAY = date(2026, 8, 17)


@pytest.fixture()
def fx(db):
    return FxService(db)


def rate(db, day, base, quote, value, *, carried=False):
    db.add(FxRate(day=day, base=base, quote=quote, rate=value,
                  is_carried_forward=carried))
    db.commit()


# --- the rate itself ------------------------------------------------------------------

def test_the_same_currency_is_always_one(fx):
    """Short-circuits without touching the table. Otherwise every EUR→EUR conversion would need
    a row that has no business existing."""
    value, day, carried = fx.rate_for(DAY, "EUR", "EUR")
    assert value == Decimal(1)
    assert carried is False


def test_an_exact_day_is_used_as_is(db, fx):
    rate(db, DAY, "USD", "EUR", Decimal("0.92"))
    value, day, carried = fx.rate_for(DAY, "USD", "EUR")

    assert value == Decimal("0.92")
    assert day == DAY
    assert carried is False


def test_a_past_amount_uses_that_days_rate(db, fx):
    """**The assertion story 018 exists for.** Today's rate applied to a year-old sale makes the
    whole history move every morning."""
    rate(db, date(2025, 8, 17), "USD", "EUR", Decimal("0.80"))
    rate(db, DAY, "USD", "EUR", Decimal("0.92"))

    converted = fx.convert(10_000, day=date(2025, 8, 17), base="USD", quote="EUR")

    assert converted.cents == 8_000
    assert converted.rate_day == date(2025, 8, 17)


def test_a_missing_day_carries_the_previous_rate_forward(db, fx):
    """Rates are not published at weekends. Carrying forward is right; doing it *silently* is not
    — which is what `approximate` is for."""
    rate(db, date(2026, 8, 14), "USD", "EUR", Decimal("0.90"))

    value, day, carried = fx.rate_for(date(2026, 8, 16), "USD", "EUR")

    assert value == Decimal("0.90")
    assert day == date(2026, 8, 14)
    assert carried is True


def test_a_carried_conversion_is_marked_approximate(db, fx):
    rate(db, date(2026, 8, 14), "USD", "EUR", Decimal("0.90"))
    converted = fx.convert(1_000, day=date(2026, 8, 16), base="USD", quote="EUR")

    assert converted.approximate is True


def test_an_exact_conversion_is_not_marked_approximate(db, fx):
    rate(db, DAY, "USD", "EUR", Decimal("0.90"))
    assert fx.convert(1_000, day=DAY, base="USD", quote="EUR").approximate is False


def test_carrying_forward_stops_at_the_window(db, fx):
    """A weekend's carry-forward is fine. A month's is a broken job, and at that distance the
    flag stops being a caveat and starts being an excuse — so it refuses instead."""
    rate(db, DAY, "USD", "EUR", Decimal("0.90"))

    with pytest.raises(NoRateAvailable):
        fx.rate_for(DAY + timedelta(days=MAX_CARRY_FORWARD_DAYS + 1), "USD", "EUR")


def test_no_rate_at_all_is_refused_rather_than_guessed(fx):
    with pytest.raises(NoRateAvailable):
        fx.rate_for(DAY, "JPY", "EUR")


def test_a_future_rate_is_not_used_for_a_past_day(db, fx):
    """Only rates at or before the day. Reaching forwards would be the same error as using
    today's rate, dressed differently."""
    rate(db, date(2026, 12, 1), "USD", "EUR", Decimal("0.50"))

    with pytest.raises(NoRateAvailable):
        fx.rate_for(DAY, "USD", "EUR")


# --- the arithmetic -------------------------------------------------------------------

def test_money_stays_in_cents(db, fx):
    """Cents in, cents out, with an explicit currency at both ends — standards §3. Rounding
    happens once, at the end; a float in the middle is how a total stops matching the sum of its
    parts, which a collector notices and cannot explain."""
    rate(db, DAY, "USD", "EUR", Decimal("0.925"))
    converted = fx.convert(1_999, day=DAY, base="USD", quote="EUR")

    assert isinstance(converted.cents, int)
    assert converted.cents == 1_849  # 1999 × 0.925 = 1849.075, half-up


def test_the_original_amount_stays_visible(db, fx):
    """Story 018's second criterion. A converted figure with no way back to what was actually
    paid is unauditable — and this whole product's claim is that its numbers are checkable."""
    rate(db, DAY, "USD", "EUR", Decimal("0.92"))
    converted = fx.convert(5_000, day=DAY, base="USD", quote="EUR")

    assert converted.original_cents == 5_000
    assert converted.original_currency == "USD"
    assert converted.currency == "EUR"


def test_rounding_is_half_up_not_truncation(db, fx):
    rate(db, DAY, "USD", "EUR", Decimal("1.005"))
    assert fx.convert(1_000, day=DAY, base="USD", quote="EUR").cents == 1_005


def test_currency_codes_are_normalised(db, fx):
    rate(db, DAY, "USD", "EUR", Decimal("0.92"))
    assert fx.convert(1_000, day=DAY, base="usd", quote="eur").cents == 920


# --- storing --------------------------------------------------------------------------

def test_storing_a_days_rates(db, fx):
    written = fx.store(DAY, {("EUR", "USD"): Decimal("1.09"), ("USD", "EUR"): Decimal("0.92")})
    assert written == 2
    assert fx.rate_for(DAY, "USD", "EUR")[0] == Decimal("0.92")


def test_storing_twice_corrects_rather_than_duplicates(db, fx):
    """`(day, base, quote)` is the primary key, so a re-fetch corrects the stored rate rather
    than adding a second opinion about it — which makes the daily job safe to re-run."""
    fx.store(DAY, {("USD", "EUR"): Decimal("0.90")})
    fx.store(DAY, {("USD", "EUR"): Decimal("0.92")})

    assert fx.rate_for(DAY, "USD", "EUR")[0] == Decimal("0.92")
    assert db.query(FxRate).count() == 1


def test_carry_forward_writes_flagged_rows(db, fx):
    """Stored explicitly rather than left for `rate_for` to paper over. Both produce the right
    number; only one shows in the table that the job has been failing."""
    fx.store(date(2026, 8, 14), {
        ("USD", "EUR"): Decimal("0.90"), ("GBP", "EUR"): Decimal("1.17"),
    })

    copied = fx.carry_forward(date(2026, 8, 15))

    assert copied == 2
    row = db.get(FxRate, (date(2026, 8, 15), "USD", "EUR"))
    assert row.is_carried_forward is True
    assert Decimal(str(row.rate)) == Decimal("0.90")


def test_carrying_forward_with_no_history_does_nothing(fx):
    assert fx.carry_forward(DAY) == 0
