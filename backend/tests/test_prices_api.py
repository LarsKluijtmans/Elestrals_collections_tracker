"""The price surfaces — story 030 and story 032.

What is asserted here is mostly about *honesty of presentation*: that an empty state is an empty
state rather than a zero, that every figure carries its observation count and confidence, that a
stale rollup says so, and that no raw listing ever reaches a non-admin.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.inventory_item import InventoryItem
from app.models.price_daily import PriceDaily
from app.security import Principal, verify_token
from app.models.base import utc_today
from test_inventory import ALICE, seed_catalog

TODAY = utc_today()


def principal(sub: str) -> Principal:
    return Principal(sub=sub, project_id="p", company_id="c", email=None,
                     username=None, scope="", token_type="access")


@pytest.fixture()
def catalog(db):
    return seed_catalog(db, card_count=3)


@pytest.fixture()
def api(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[verify_token] = lambda: principal(ALICE)
    yield TestClient(app)
    app.dependency_overrides.clear()


def price(db, printing_id: str, *, cents: int, day: date | None = None,
          confidence: str = "high", observations: int = 6, computed=None,
          sale_type: str = "sold") -> None:
    db.add(PriceDaily(
        id=str(uuid.uuid4()), printing_id=printing_id, sealed_product_id=None,
        condition="near_mint", product_key=printing_id, product_kind="printing",
        condition_key="near_mint", day=day or TODAY, currency="EUR", sale_type=sale_type,
        low_cents=cents, median_cents=cents, high_cents=cents, mean_cents=cents,
        observation_count=observations, source_count=2, excluded_count=0,
        confidence=confidence, computed_at=computed or datetime.now(timezone.utc),
    ))
    db.commit()


# --- the price tab -------------------------------------------------------------------

def test_a_printing_with_no_data_gets_an_honest_empty_state(api, catalog):
    """Not a flat line at zero. A chart at zero reads as "this card is worthless", which is a
    different and false claim from "we have not seen one sell"."""
    pid = catalog["printings"]["BS1-001:common"]

    body = api.get(f"/api/v1/prices/printings/{pid}").json()

    assert body["is_empty"] is True
    assert body["points"] == []


def test_every_point_carries_its_count_and_confidence(api, db, catalog):
    """A median from two sales and a median from two hundred are the same number and mean very
    different things."""
    pid = catalog["printings"]["BS1-001:common"]
    price(db, pid, cents=1234)

    point = api.get(f"/api/v1/prices/printings/{pid}").json()["points"][0]

    assert point["median_cents"] == 1234
    assert point["observation_count"] == 6
    assert point["confidence"] == "high"


def test_the_range_filter_narrows_the_series(api, db, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    price(db, pid, cents=1000, day=TODAY - timedelta(days=200))
    price(db, pid, cents=1100, day=TODAY)

    thirty = api.get(f"/api/v1/prices/printings/{pid}", params={"range": "30d"}).json()
    everything = api.get(f"/api/v1/prices/printings/{pid}", params={"range": "all"}).json()

    assert len(thirty["points"]) == 1
    assert len(everything["points"]) == 2


def test_asking_prices_are_a_separate_series(api, db, catalog):
    """`sold` and `listed` are never mixed. The tab asks for one or the other and labels it."""
    pid = catalog["printings"]["BS1-001:common"]
    price(db, pid, cents=1000, sale_type="sold")
    price(db, pid, cents=4000, sale_type="listed", confidence="low")

    sold = api.get(f"/api/v1/prices/printings/{pid}").json()
    listed = api.get(
        f"/api/v1/prices/printings/{pid}", params={"sale_type": "listed"}
    ).json()

    assert sold["points"][0]["median_cents"] == 1000
    assert listed["points"][0]["median_cents"] == 4000
    assert listed["points"][0]["confidence"] == "low"


def test_a_stale_rollup_says_so(api, db, catalog):
    """`harvest-api` being down degrades freshness, never availability — so the figure is served
    and labelled rather than withheld."""
    pid = catalog["printings"]["BS1-001:common"]
    price(db, pid, cents=1000, computed=datetime.now(timezone.utc) - timedelta(days=9))

    body = api.get(f"/api/v1/prices/printings/{pid}").json()

    assert body["is_stale"] is True
    assert body["points"], "still served — a stale price is better than a blank page"


def test_the_response_carries_no_listing_level_data(api, db, catalog):
    """Rollups only. Raw listings, match notes and rejection reasons are admin-only, and not
    because they are secret — because they are uneven scraped material and showing them to a
    collector as a product would misrepresent what they are."""
    pid = catalog["printings"]["BS1-001:common"]
    price(db, pid, cents=1000)

    body = api.get(f"/api/v1/prices/printings/{pid}").json()

    serialised = str(body)
    for leak in ("source_url", "match_note", "external_id", "title"):
        assert leak not in serialised


# --- the market overview -------------------------------------------------------------

def test_movers_need_a_minimum_observation_count(api, db, catalog):
    """Without it the list is dominated by printings with one sale each — the data least worth
    ranking, presented as the most interesting."""
    noisy = catalog["printings"]["BS1-001:common"]
    price(db, noisy, cents=100, day=TODAY - timedelta(days=10), observations=1)
    price(db, noisy, cents=9000, day=TODAY - timedelta(days=1), observations=1)

    body = api.get("/api/v1/prices/overview").json()

    assert body["movers_up"] == []
    assert body["min_observations"] == 3


def test_a_real_mover_appears_with_its_change(api, db, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    price(db, pid, cents=1000, day=TODAY - timedelta(days=10), observations=5)
    price(db, pid, cents=2000, day=TODAY - timedelta(days=1), observations=5)

    body = api.get("/api/v1/prices/overview").json()

    assert body["movers_up"], "a doubling over the window should rank"
    assert body["movers_up"][0]["change_pct"] == pytest.approx(100.0)


# --- the portfolio ---------------------------------------------------------------------

def test_the_portfolio_states_its_coverage(api, db, catalog):
    priced = catalog["printings"]["BS1-001:common"]
    unpriced = catalog["printings"]["BS1-002:common"]
    price(db, priced, cents=1000)
    db.add_all([
        InventoryItem(user_sub=ALICE, printing_id=priced, condition="near_mint",
                      quantity=1, merge_condition="near_mint"),
        InventoryItem(user_sub=ALICE, printing_id=unpriced, condition="near_mint",
                      quantity=1, merge_condition="near_mint"),
    ])
    db.commit()

    body = api.get("/api/v1/portfolio").json()

    assert body["total_cents"] == 1000
    assert body["valued_items"] == 1
    assert body["unvalued_items"] == 1
    assert body["coverage"] == 0.5
    assert body["unvalued_reasons"] == {"no_data": 1}


def test_an_empty_portfolio_is_empty_not_worthless(api):
    body = api.get("/api/v1/portfolio").json()

    assert body["total_cents"] == 0
    assert body["valued_items"] == 0
    assert body["coverage"] == 0.0


def test_the_portfolio_is_scoped_to_the_caller(api, db, catalog):
    """`user_sub` comes from the validated token and nowhere else — the phase-1 rule that
    ownership is a signature rather than a filter applies here too."""
    pid = catalog["printings"]["BS1-001:common"]
    price(db, pid, cents=1000)
    db.add(InventoryItem(user_sub="someone-else", printing_id=pid, condition="near_mint",
                         quantity=5, merge_condition="near_mint"))
    db.commit()

    body = api.get("/api/v1/portfolio").json()

    assert body["total_cents"] == 0
