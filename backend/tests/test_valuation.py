"""Collection valuation — story 020.

One rule carries this file: **an item with no price is excluded and counted, never treated as
zero.** A zero for an unpriced holding produces a total that is confidently wrong and silently
low; a stated coverage produces one that is honestly partial. The second is usable and the first
is not, and nobody reading the number can tell them apart unless we say so.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.inventory_item import InventoryItem
from app.models.price_daily import PriceDaily
from app.repositories.price_repository import PriceRepository
from app.services.valuation_service import ValuationService
from test_inventory import ALICE, seed_catalog

TODAY = date.today()


@pytest.fixture()
def catalog(db):
    return seed_catalog(db, card_count=3)


@pytest.fixture()
def service(db) -> ValuationService:
    return ValuationService(PriceRepository(db))


def price(db, printing_id: str, *, cents: int, condition: str = "near_mint",
          confidence: str = "high", day: date | None = None, sale_type: str = "sold",
          observations: int = 6) -> None:
    db.add(PriceDaily(
        id=str(uuid.uuid4()), printing_id=printing_id, sealed_product_id=None,
        condition=condition, product_key=printing_id, product_kind="printing",
        condition_key=condition or "", day=day or TODAY, currency="EUR", sale_type=sale_type,
        low_cents=cents, median_cents=cents, high_cents=cents, mean_cents=cents,
        observation_count=observations, source_count=2, excluded_count=0,
        confidence=confidence, computed_at=datetime.now(timezone.utc),
    ))
    db.commit()


def hold(db, printing_id: str, *, quantity: int = 1, condition: str = "near_mint",
         graded: bool = False) -> InventoryItem:
    item = InventoryItem(
        user_sub=ALICE, printing_id=printing_id, condition=condition, quantity=quantity,
        is_graded=graded, merge_condition=None if graded else condition,
    )
    db.add(item)
    db.commit()
    return item


def test_a_priced_holding_is_quantity_times_the_median(db, catalog, service):
    pid = catalog["printings"]["BS1-001:common"]
    price(db, pid, cents=1000)
    items = [hold(db, pid, quantity=3)]

    result = service.value(items)

    assert result.total_cents == 3000
    assert result.valued_items == 3
    assert result.unvalued_items == 0
    assert result.coverage == 1.0


def test_an_unpriced_holding_is_excluded_and_counted_never_zero(db, catalog, service):
    """The rule with teeth. A total that quietly counts unpriced cards as worthless is worse
    than one that says it covered 1 of 3."""
    priced = catalog["printings"]["BS1-001:common"]
    unpriced = catalog["printings"]["BS1-002:common"]
    price(db, priced, cents=1000)
    items = [hold(db, priced), hold(db, unpriced, quantity=2)]

    result = service.value(items)

    assert result.total_cents == 1000, "the unpriced two contribute nothing, not zero euros each"
    assert result.valued_items == 1
    assert result.unvalued_items == 2
    assert result.unvalued_reasons == {"no_data": 2}
    assert result.coverage == pytest.approx(1 / 3)


def test_the_unvalued_items_are_identifiable_not_just_counted(db, catalog, service):
    """A count is informative; knowing which ones is actionable, and it is usually the same lead
    the admin console works from."""
    unpriced = catalog["printings"]["BS1-002:common"]
    item = hold(db, unpriced)

    result = service.value([item])

    assert result.unvalued_item_ids == [item.id]


def test_a_graded_holding_is_excluded_with_its_own_reason(db, catalog, service):
    """The matcher refuses graded slabs on purpose — a PSA 10 and a raw copy are two markets —
    so there is no graded price to value this with, and saying so is correct."""
    pid = catalog["printings"]["BS1-001:common"]
    price(db, pid, cents=1000)
    items = [hold(db, pid, graded=True)]

    result = service.value(items)

    assert result.total_cents == 0
    assert result.unvalued_reasons == {"graded": 1}


def test_a_different_condition_is_never_substituted(db, catalog, service):
    """A Heavily Played copy priced at the Near Mint median is a wrong number with a plausible
    face, which is the worst kind."""
    pid = catalog["printings"]["BS1-001:common"]
    price(db, pid, cents=5000, condition="near_mint")
    items = [hold(db, pid, condition="heavily_played")]

    result = service.value(items)

    assert result.total_cents == 0
    assert result.unvalued_reasons == {"no_data": 1}


def test_an_unstated_condition_rollup_is_used_as_the_fallback(db, catalog, service):
    """The unstated bucket is a real one, and a holding whose exact condition has no rollup may
    fall back to it — but only to it."""
    pid = catalog["printings"]["BS1-001:common"]
    price(db, pid, cents=800, condition=None)
    items = [hold(db, pid, condition="lightly_played")]

    result = service.value(items)

    assert result.total_cents == 800


def test_valuation_reads_sold_only(db, catalog, service):
    """An asking price is not evidence that anyone paid it."""
    pid = catalog["printings"]["BS1-001:common"]
    price(db, pid, cents=9999, sale_type="listed")
    items = [hold(db, pid)]

    result = service.value(items)

    assert result.total_cents == 0
    assert result.unvalued_reasons == {"no_data": 1}


def test_the_overall_confidence_is_the_weakest_link(db, catalog, service):
    """A total that is 90% `high` and 10% `low` is not a `high`-confidence total, and rounding
    that up is exactly the flattery this product exists not to do."""
    good = catalog["printings"]["BS1-001:common"]
    thin = catalog["printings"]["BS1-002:common"]
    price(db, good, cents=1000, confidence="high")
    price(db, thin, cents=100, confidence="low", observations=1)

    result = service.value([hold(db, good), hold(db, thin)])

    assert result.confidence == "low"


def test_the_most_recent_day_wins(db, catalog, service):
    pid = catalog["printings"]["BS1-001:common"]
    price(db, pid, cents=1000, day=TODAY - timedelta(days=5))
    price(db, pid, cents=1500, day=TODAY)

    result = service.value([hold(db, pid)])

    assert result.total_cents == 1500


def test_an_empty_collection_values_at_zero_with_no_coverage(db, service):
    result = service.value([])

    assert result.total_cents == 0
    assert result.total_items == 0
    assert result.coverage == 0.0
