"""The admin API end to end — stories 025, 026 and 027.

Runs the real app against the in-memory database, with the admin gate satisfied by a dependency
override. What is under test is the *behaviour an admin sees*: the filters that make the explorer
usable, the `409` that stops a double-click becoming two scans, and the stop flag.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.core.dependencies import require_admin
from app.core.security import Principal
from app.main import app as real_app
from app.models.market_listing import MarketListing
from app.repositories.harvest_repository import HarvestRepository

NOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def registered_connector():
    """The trigger endpoint refuses a config row with no connector — an orphaned row is a real
    state and must not be startable. So these tests need one registered."""
    from app.harvest.canonical import HarvestDescriptor
    from app.harvest.sources import SOURCES, register

    class Stub:
        name = "fake"

        def describe(self) -> HarvestDescriptor:
            return HarvestDescriptor(
                name="fake", display_name="Fake source", host="fake.test",
                access_mode="scrape", reports_sold=False,
            )

        def bind(self, client) -> None:
            pass

        def discover(self, query, *, limit):
            return []

        def recheck(self, external_ids):
            return []

    register("fake", Stub)
    try:
        yield
    finally:
        SOURCES.pop("fake", None)


@pytest.fixture()
def client(db, registered_connector):
    real_app.dependency_overrides[get_db] = lambda: db
    real_app.dependency_overrides[require_admin] = lambda: Principal(
        sub="admin-1", project_id="p", company_id="c", email=None, username=None,
        scope="elestrals:admin", token_type="access",
    )
    with TestClient(real_app) as test_client:
        yield test_client
    real_app.dependency_overrides.clear()


def add_listing(db, source, **overrides) -> MarketListing:
    values = dict(
        source_id=source.id, external_id="listing-1", title="Elestrals Vipyro FE01 012/126",
        url="https://fake.test/item/1", kind="single", printing_id="p-normal",
        condition="near_mint", match_confidence=0.95, match_note="card: Vipyro; set: FE01",
        price_cents=1234, currency="USD", quantity=1, buying_format="fixed",
        status="active", first_seen_at=NOW, last_seen_at=NOW,
    )
    values.update(overrides)
    row = MarketListing(**values)
    db.add(row)
    db.commit()
    return row


# --- the explorer (story 025) -------------------------------------------------------------

def test_the_explorer_lists_listings_with_their_match_notes(client, db, source, catalog_rows):
    add_listing(db, source)

    body = client.get("/api/v1/admin/listings").json()

    assert body["total"] == 1
    item = body["items"][0]
    assert item["source_key"] == "fake"
    assert item["match_note"] == "card: Vipyro; set: FE01"
    assert item["product_label"] == "Vipyro · FE01 012 · normal", "resolved from the catalog"


def test_the_unmatched_queue_is_one_filter_away(client, db, source, catalog_rows):
    """An unmatched listing is a lead — either a product missing from the catalog or a matcher
    gap — and reaching them has to be trivial or nobody will."""
    add_listing(db, source)
    add_listing(
        db, source, external_id="listing-2", printing_id=None, match_confidence=0,
        match_note="no catalog card or product name found in the title", kind="unknown",
    )

    body = client.get("/api/v1/admin/listings", params={"matched": False}).json()

    assert body["total"] == 1
    assert body["items"][0]["external_id"] == "listing-2"
    assert body["items"][0]["product_label"] is None


def test_a_confidence_band_can_be_filtered(client, db, source, catalog_rows):
    add_listing(db, source, match_confidence=0.95)
    add_listing(db, source, external_id="listing-2", match_confidence=0.40)

    body = client.get("/api/v1/admin/listings", params={"max_confidence": 0.7}).json()

    assert [i["external_id"] for i in body["items"]] == ["listing-2"]


def test_an_ended_listing_reports_its_real_status(client, db, source, catalog_rows):
    """`ended_unknown` is returned raw so the UI can label it "ended, reason unknown". Describing
    it loosely as sold would undo the whole invariant chain in one word."""
    add_listing(db, source, status="ended_unknown", ended_at=NOW)

    body = client.get("/api/v1/admin/listings").json()

    assert body["items"][0]["status"] == "ended_unknown"
    assert body["items"][0]["sold_price_cents"] is None


def test_a_missing_listing_is_a_404(client):
    assert client.get("/api/v1/admin/listings/nope").status_code == 404


# --- health (story 026) ----------------------------------------------------------------------

def test_source_health_shows_the_accepted_risk_next_to_the_source(client, db, source):
    """ADR-004 accepts a risk per source. Putting the note and the person who accepted it where
    an admin sees them every time they look at the pipeline is what keeps "reviewed: yes" from
    being enough."""
    body = client.get("/api/v1/admin/sources").json()

    row = next(item for item in body if item["key"] == "fake")
    assert "prohibit" in row["tos_review_note"]
    assert row["risk_accepted_by"] == "Test Suite"
    assert row["never_run"] is True, "distinct from 'ran and found nothing'"


def test_a_quarantined_source_is_visibly_distinct(client, db, source):
    source.quarantined_until = datetime.now(timezone.utc) + timedelta(hours=2)
    source.quarantine_reason = "5 refusals in one run"
    source.quarantine_level = 1
    db.commit()

    row = next(item for item in client.get("/api/v1/admin/sources").json()
               if item["key"] == "fake")

    assert row["quarantined"] is True
    assert row["quarantine_reason"] == "5 refusals in one run"
    assert row["quarantined_until"] is not None


def test_the_kill_switch_works_without_a_deploy(client, db, source):
    response = client.post("/api/v1/admin/sources/fake/disable")

    assert response.status_code == 200
    db.refresh(source)
    assert source.enabled is False


def test_enabling_a_source_is_not_an_api_action(client):
    """Accepting a contractual risk is a deliberate act with a note and a name. There is no
    endpoint for it, and that is the unit brief's decision rather than an oversight."""
    assert client.post("/api/v1/admin/sources/fake/enable").status_code == 404


# --- running a scan (story 027) ---------------------------------------------------------------

def test_a_second_run_of_the_same_source_and_mode_is_refused(client, db, source, monkeypatch):
    """Refused, not silently queued. Silently queueing makes an admin press the button twice and
    then get two scans an hour apart."""
    HarvestRepository(db).start_run(source.id, "deep")

    response = client.post("/api/v1/admin/sources/fake/scan/deep")

    assert response.status_code == 409
    assert "already running" in response.json()["error"]["message"]


def test_triggering_returns_a_run_id_immediately(client, db, source, monkeypatch):
    """`202` with an id, not a four-hour HTTP request."""
    queued: list[dict] = []
    monkeypatch.setattr(
        "app.tasks.scans.run_scan.delay", lambda **kwargs: queued.append(kwargs)
    )

    response = client.post("/api/v1/admin/sources/fake/scan/light")

    assert response.status_code == 202
    body = response.json()
    assert body["run_id"]
    assert queued == [{"source_key": "fake", "mode": "light", "run_id": body["run_id"]}]
    assert response.headers["Location"].endswith(body["run_id"])


def test_a_broker_outage_does_not_leave_a_phantom_run(client, db, source, monkeypatch):
    """The run row is created before the task is queued, so a broker failure has to clean up
    after itself or the console shows a scan that will never start."""
    def explode(**kwargs):
        raise RuntimeError("redis is down")

    monkeypatch.setattr("app.tasks.scans.run_scan.delay", explode)

    response = client.post("/api/v1/admin/sources/fake/scan/deep")

    assert response.status_code == 503
    runs = HarvestRepository(db).list_runs()
    assert runs and runs[0].status == "failed"
    assert "could not queue" in runs[0].error_summary


def test_stopping_a_run_sets_the_flag_the_scan_checks(client, db, source):
    run = HarvestRepository(db).start_run(source.id, "deep")

    response = client.post(f"/api/v1/admin/runs/{run.id}/stop")

    assert response.status_code == 200
    db.refresh(run)
    assert run.stop_requested is True
    assert run.status == "running", "the scan ends it, not the endpoint"


def test_stopping_a_finished_run_is_a_conflict(client, db, source):
    harvest = HarvestRepository(db)
    run = harvest.start_run(source.id, "deep")
    harvest.finish_run(run, status="success", counts={})

    assert client.post(f"/api/v1/admin/runs/{run.id}/stop").status_code == 409


def test_an_unknown_mode_is_rejected(client, source):
    assert client.post("/api/v1/admin/sources/fake/scan/sideways").status_code in (400, 404)
