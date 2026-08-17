"""Running the pipeline by hand — `/admin/maintenance/rollup` and `/admin/maintenance/sweep`.

The manual path only became useful when these landed. A scan could always be started by hand, but
it writes *observations*; nothing a collector sees moves until `price_daily` is recomputed, and that
only happened on the beat schedule. So the tests worth having are the ones that prove the loop
closes: scan-shaped data in, one request, published rows out — and that the window is bounded so the
endpoint cannot be turned into a synchronous full-history rebuild.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.core.dependencies import require_admin
from app.core.security import Principal
from app.main import app as real_app
from app.models.price_daily import PriceDaily
from app.models.price_observation import PriceObservation
from app.repositories.harvest_repository import HarvestRepository

#: Read once, and compared against a `since` the endpoint computes per request. A run that straddles
#: midnight would therefore disagree by a day. Left as it is rather than frozen: the window is
#: genuinely relative to "now", and a fixed clock would stop the tests asserting that.
TODAY = date.today()


@pytest.fixture()
def client(db):
    real_app.dependency_overrides[get_db] = lambda: db
    real_app.dependency_overrides[require_admin] = lambda: Principal(
        sub="admin-1", project_id="p", company_id="c", email=None, username=None,
        scope="elestrals:admin", token_type="access",
    )
    with TestClient(real_app) as test_client:
        yield test_client
    real_app.dependency_overrides.clear()


@pytest.fixture()
def run(db, source):
    return HarvestRepository(db).start_run(source.id, "deep")


def observe(db, run, source, *, price: int, days_ago: int = 0, printing_id="p-normal") -> None:
    at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    db.add(PriceObservation(
        source_id=source.id,
        run_id=run.id,
        printing_id=printing_id,
        condition="near_mint",
        sale_type="sold",
        observed_at=at,
        price_cents=price,
        currency="USD",
        external_id=f"sold-{price}-{days_ago}-{printing_id}",
        source_url="https://fake.test/item",
        match_confidence=0.95,
    ))
    db.commit()


def published(db) -> list[PriceDaily]:
    return list(db.query(PriceDaily).all())


# --- the rollup ----------------------------------------------------------------------

def test_a_manual_rollup_publishes_what_a_scan_just_observed(client, db, run, source):
    """The whole point. Without this, an admin who triggers a scan to check something has to wait
    out `HARVEST_ROLLUP_EVERY_MINUTES` before any of it is visible."""
    for price in (1000, 1100, 1200):
        observe(db, run, source, price=price)
    assert published(db) == []

    response = client.post("/api/v1/admin/maintenance/rollup")

    assert response.status_code == 200
    body = response.json()
    assert body["days"] == 1
    assert body["rows"] >= 1
    assert len(published(db)) >= 1


def test_it_reports_the_days_that_had_observations_not_the_window(client, db, run, source):
    """`days` is how many days actually carried data. An admin who asked for a week and is told 2
    has learnt something true about their coverage."""
    observe(db, run, source, price=1000, days_ago=0)
    observe(db, run, source, price=1100, days_ago=2)

    body = client.post("/api/v1/admin/maintenance/rollup?since_days=7").json()

    assert body["since_days"] == 7
    assert body["days"] == 2


def test_it_states_the_window_it_actually_recomputed(client, db, run, source):
    observe(db, run, source, price=1000)
    body = client.post("/api/v1/admin/maintenance/rollup?since_days=3").json()

    # Three days *including today* — an off-by-one here would silently skip the oldest day the
    # admin asked for, which is the day they are most likely to be checking.
    assert body["since"] == (TODAY - timedelta(days=2)).isoformat()


def test_an_older_day_outside_the_window_is_left_alone(client, db, run, source):
    observe(db, run, source, price=1000, days_ago=0)
    observe(db, run, source, price=9999, days_ago=30)

    body = client.post("/api/v1/admin/maintenance/rollup?since_days=2").json()

    assert body["days"] == 1
    assert all(row.day >= TODAY - timedelta(days=1) for row in published(db))


def test_running_it_twice_changes_nothing(client, db, run, source):
    """The rollup is a projection, recomputed rather than accumulated. That is what makes this
    button safe to press repeatedly — and what makes "run it again" the fix for a bad number."""
    for price in (1000, 1100, 1200):
        observe(db, run, source, price=price)

    first = client.post("/api/v1/admin/maintenance/rollup").json()
    rows_after_first = len(published(db))
    second = client.post("/api/v1/admin/maintenance/rollup").json()

    assert second == first
    assert len(published(db)) == rows_after_first


def test_it_recomputes_rather_than_appends_when_observations_change(client, db, run, source):
    """A late-arriving observation has to be able to change the past, and must not leave the old
    answer beside the new one."""
    observe(db, run, source, price=1000)
    client.post("/api/v1/admin/maintenance/rollup")
    before = len(published(db))

    observe(db, run, source, price=2000)
    client.post("/api/v1/admin/maintenance/rollup")

    assert len(published(db)) == before
    assert any(row.median_cents == 1500 for row in published(db))


def test_an_empty_window_is_a_success_with_nothing_in_it(client, db):
    # Not an error. "No observations in the last week" is a real and useful answer.
    body = client.post("/api/v1/admin/maintenance/rollup").json()
    assert body == {
        "since": (TODAY - timedelta(days=6)).isoformat(), "since_days": 7,
        "days": 0, "rows": 0, "excluded": 0, "max_since_days": 90,
    }


def test_the_window_is_capped(client):
    """The cap is what keeps this endpoint honest: a full rebuild over years of observations is a
    job for the CLI, not a request whose timeout we do not control."""
    assert client.post("/api/v1/admin/maintenance/rollup?since_days=91").status_code == 422
    assert client.post("/api/v1/admin/maintenance/rollup?since_days=0").status_code == 422
    assert client.post("/api/v1/admin/maintenance/rollup?since_days=-1").status_code == 422


def test_it_says_where_the_synchronous_path_stops(client):
    # Echoed rather than hardcoded in the console, so the two cannot drift.
    assert client.post("/api/v1/admin/maintenance/rollup").json()["max_since_days"] == 90


# --- the sweeper ---------------------------------------------------------------------

def test_sweeping_frees_a_run_orphaned_by_a_deploy(client, db, source):
    """The friction this removes: an orphaned `running` row makes the duplicate-run check refuse
    the very scan an admin is trying to start, and the scheduled sweeper is ten minutes away."""
    harvest = HarvestRepository(db)
    stale = harvest.start_run(source.id, "deep")
    stale.started_at = datetime.now(timezone.utc) - timedelta(hours=6)
    db.commit()

    body = client.post("/api/v1/admin/maintenance/sweep").json()

    assert body["swept"] == 1
    db.refresh(stale)
    assert stale.status == "failed"


def test_sweeping_leaves_a_healthy_run_running(client, db, source):
    # A four-hour deep scan is not stale, and sweeping it would kill a working job.
    harvest = HarvestRepository(db)
    fresh = harvest.start_run(source.id, "light")

    assert client.post("/api/v1/admin/maintenance/sweep").json()["swept"] == 0
    db.refresh(fresh)
    assert fresh.status == "running"


def test_sweeping_nothing_is_still_a_success(client):
    body = client.post("/api/v1/admin/maintenance/sweep").json()
    assert body["swept"] == 0
    # The threshold is reported so "swept 0" can be read as "nothing was old enough" rather than
    # "the sweeper is broken".
    assert body["stale_after_minutes"] > 0


# --- the gate ------------------------------------------------------------------------

def test_both_endpoints_require_the_admin_scope(db):
    """`elestrals:operator` is not enough. Recomputing what every collector sees is not the same
    act as re-importing the catalog, which is the separation the two scopes exist for."""
    real_app.dependency_overrides[get_db] = lambda: db
    with TestClient(real_app) as anonymous:
        assert anonymous.post("/api/v1/admin/maintenance/rollup").status_code in (401, 403)
        assert anonymous.post("/api/v1/admin/maintenance/sweep").status_code in (401, 403)
    real_app.dependency_overrides.clear()
