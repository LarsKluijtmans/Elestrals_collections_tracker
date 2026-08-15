"""Observations → `price_daily`: outliers, confidence, and re-runnability.

Three properties, and each one is a promise made elsewhere in the product:

* **Outliers are excluded from the median and flagged, not deleted** — because the admin
  distribution view draws them, and because a silently dropped point makes the rollup
  unauditable.
* **Confidence follows the stated rule exactly**, including that anything derived from `listed`
  prices is `low` however much of it there is. The number of people asking a price says nothing
  about whether anyone paid it.
* **Re-running produces the same answer.** The rollup is a projection; that is what makes a bug
  in it fixable by re-running rather than by a data migration.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.price_daily import PriceDaily
from app.models.price_observation import PriceObservation
from app.repositories.harvest_repository import HarvestRepository
from app.services.rollup_service import RollupService, confidence_for, split_outliers

DAY = date(2026, 8, 12)
AT = datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc)


@pytest.fixture()
def service(db) -> RollupService:
    return RollupService(harvest=HarvestRepository(db))


def observe(db, run_id: str, source_id: str, price: int, *, sale_type="sold",
            printing_id="p-normal", source_suffix="", at=AT) -> None:
    db.add(PriceObservation(
        source_id=source_id + source_suffix,
        run_id=run_id,
        printing_id=printing_id,
        condition="near_mint",
        sale_type=sale_type,
        observed_at=at,
        price_cents=price,
        currency="USD",
        external_id=f"{sale_type}-{price}-{source_suffix}-{at.isoformat()}",
        source_url="https://fake.test/item",
        match_confidence=0.95,
    ))
    db.commit()


@pytest.fixture()
def run(db, source):
    return HarvestRepository(db).start_run(source.id, "deep")


def daily(db) -> list[PriceDaily]:
    return list(db.query(PriceDaily).all())


# --- the IQR rule -----------------------------------------------------------------------

class TestOutlierRule:
    def test_below_four_points_nothing_is_excluded(self):
        """An interquartile range over three points is not a statistic, and applying one would
        drop half the data and call the rest confident."""
        kept, excluded = split_outliers([100, 200, 90_000], factor=3.0, min_points=4)

        assert excluded == []
        assert kept == [100, 200, 90_000]

    def test_a_wild_point_is_excluded(self):
        values = [1000, 1050, 1100, 1150, 1200, 900_000]

        kept, excluded = split_outliers(values, factor=3.0, min_points=4)

        assert excluded == [900_000]
        assert 900_000 not in kept

    def test_identical_values_have_no_outliers(self):
        kept, excluded = split_outliers([500] * 6, factor=3.0, min_points=4)

        assert excluded == []
        assert len(kept) == 6


# --- the confidence rule ------------------------------------------------------------------

class TestConfidenceRule:
    def test_five_sold_from_two_sources_is_high(self):
        assert confidence_for(sale_type="sold", observations=5, sources=2) == "high"

    def test_five_sold_from_one_source_is_only_medium(self):
        """Volume from a single source is not corroboration — and under ADR-004, where every
        source is a connector that can be subtly wrong, that distinction earns its keep."""
        assert confidence_for(sale_type="sold", observations=5, sources=1) == "medium"

    def test_two_sold_is_medium(self):
        assert confidence_for(sale_type="sold", observations=2, sources=1) == "medium"

    def test_one_sold_is_low(self):
        assert confidence_for(sale_type="sold", observations=1, sources=1) == "low"

    @pytest.mark.parametrize("count", [1, 5, 50, 500])
    def test_asking_prices_are_low_however_many_there_are(self, count):
        """The rule with teeth. Fifty people asking £100 is not evidence that anything sold for
        £100, and valuation reads `sold` only for exactly this reason."""
        assert confidence_for(sale_type="listed", observations=count, sources=9) == "low"


# --- the job ------------------------------------------------------------------------------

def test_a_day_rolls_up_into_one_row_per_key(db, source, run, service):
    for price in (1000, 1100, 1200):
        observe(db, run.id, source.id, price)

    rows_written, excluded = service.rebuild_day(DAY)

    assert rows_written == 1
    assert excluded == 0
    row = daily(db)[0]
    assert row.median_cents == 1100
    assert row.low_cents == 1000
    assert row.high_cents == 1200
    assert row.observation_count == 3
    assert row.confidence == "medium"


def test_sold_and_listed_roll_up_separately(db, source, run, service):
    """Never blended. A card can have both; the UI picks which to show and labels it."""
    observe(db, run.id, source.id, 1000, sale_type="sold")
    observe(db, run.id, source.id, 5000, sale_type="listed")

    service.rebuild_day(DAY)

    rows = {row.sale_type: row for row in daily(db)}
    assert set(rows) == {"sold", "listed"}
    assert rows["sold"].median_cents == 1000
    assert rows["listed"].median_cents == 5000
    assert rows["listed"].confidence == "low"


def test_an_outlier_is_excluded_from_the_median_and_flagged_not_deleted(
    db, source, run, service
):
    for price in (1000, 1050, 1100, 1150, 1200):
        observe(db, run.id, source.id, price)
    observe(db, run.id, source.id, 900_000)

    service.rebuild_day(DAY)

    row = daily(db)[0]
    assert row.median_cents == 1100
    assert row.observation_count == 5, "counts what was kept, so confidence is honest"
    assert row.excluded_count == 1

    # Still there, and findable — the admin distribution view draws it.
    survivors = db.query(PriceObservation).filter(PriceObservation.price_cents == 900_000).all()
    assert len(survivors) == 1
    assert survivors[0].is_outlier is True


def test_re_running_produces_the_same_answer(db, source, run, service):
    for price in (1000, 1100, 1200, 1300):
        observe(db, run.id, source.id, price)

    service.rebuild_day(DAY)
    before = [(r.median_cents, r.observation_count, r.confidence) for r in daily(db)]
    service.rebuild_day(DAY)
    after = [(r.median_cents, r.observation_count, r.confidence) for r in daily(db)]

    assert before == after
    assert len(daily(db)) == 1, "recomputed in place, not accumulated"


def test_re_running_is_idempotent_for_a_sealed_product_too(db, source, run, service):
    """The regression that found the key columns.

    A sealed rollup has no `printing_id`, and both MySQL and SQLite treat NULLs as distinct in a
    unique index — so a key built from the nullable columns did not constrain these rows at all,
    and every re-run quietly appended a duplicate. `product_key` / `product_kind` exist for
    exactly this.
    """
    db.add(PriceObservation(
        source_id=source.id, run_id=run.id, sealed_product_id="s-box", printing_id=None,
        condition=None, sale_type="sold", observed_at=AT, price_cents=8999, currency="USD",
        external_id="sealed-1", source_url="https://fake.test/box", match_confidence=0.9,
    ))
    db.commit()

    service.rebuild_day(DAY)
    service.rebuild_day(DAY)

    rows = daily(db)
    assert len(rows) == 1, "a NULL printing_id must not defeat the unique key"
    assert rows[0].sealed_product_id == "s-box"
    assert rows[0].product_kind == "sealed"


def test_an_unstated_condition_is_its_own_bucket_and_still_deduplicates(
    db, source, run, service
):
    """A seller who does not state a condition is disproportionately selling a played card, so
    unstated is a real bucket rather than a missing value — and it has to survive a re-run."""
    observe(db, run.id, source.id, 1000)  # near_mint
    db.add(PriceObservation(
        source_id=source.id, run_id=run.id, printing_id="p-normal", condition=None,
        sale_type="sold", observed_at=AT, price_cents=800, currency="USD",
        external_id="unstated-1", source_url="https://fake.test/x", match_confidence=0.9,
    ))
    db.commit()

    service.rebuild_day(DAY)
    service.rebuild_day(DAY)

    rows = daily(db)
    assert len(rows) == 2, "two condition buckets, and neither duplicated"
    assert {r.condition_key for r in rows} == {"near_mint", ""}


def test_an_excluded_observation_is_left_out_of_the_rollup(db, source, run, service):
    """A correction is a new row plus an exclusion flag on the old one, never an edit — so the
    rollup must not see the superseded value."""
    observe(db, run.id, source.id, 1000)
    observe(db, run.id, source.id, 1100)
    wrong = db.query(PriceObservation).filter(PriceObservation.price_cents == 1100).one()
    wrong.is_excluded = True
    db.commit()

    service.rebuild_day(DAY)

    assert daily(db)[0].observation_count == 1


def test_a_day_with_no_observations_writes_nothing(db, source, run, service):
    """An absent day is absent, not zero. A rollup row at zero would draw a chart claiming the
    card became worthless."""
    observe(db, run.id, source.id, 1000, at=AT - timedelta(days=3))

    rows_written, _ = service.rebuild_day(DAY)

    assert rows_written == 0
    assert daily(db) == []


def test_rebuild_covers_every_day_that_has_observations(db, source, run, service):
    """Late-arriving data, and corrections to old days, both have to be able to change the past."""
    observe(db, run.id, source.id, 1000, at=AT)
    observe(db, run.id, source.id, 2000, at=AT - timedelta(days=5))

    result = service.rebuild()

    assert result.days == 2
    assert result.rows == 2
