"""End-to-end over both scan modes, against a fake source.

The fake is the point: every assertion here is about *our* rules — what gets stored, what gets
refused, what a second run does, what happens when a source starts refusing us — and none of them
should need a network to state. The eBay connectors' own parsing is tested separately.

The load-bearing test in this file is
`test_a_source_that_does_not_report_sales_cannot_end_a_listing_as_sold`. Everything else is
plumbing; that one is the difference between a price history and a fiction.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.harvest.canonical import HarvestDescriptor, ListingState, RawListing
from app.harvest.gate import HarvestGate
from app.harvest.http import SourceRefused
from app.harvest.quarantine import QuarantinePolicy
from app.harvest.sources import SOURCES, register
from app.models.market_listing import MarketListing
from app.models.price_observation import PriceObservation
from app.repositories.catalog_snapshot_repository import CatalogSnapshotRepository
from app.repositories.harvest_repository import HarvestRepository
from app.repositories.price_source_repository import PriceSourceRepository
from app.services.harvest_runner import HarvestRunner

HOST = "fake.test"
NOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)

MATCHED = RawListing(
    external_id="listing-1",
    title="Elestrals Vipyro FE01 012/126 Holo 1st Edition NM",
    url="https://fake.test/item/1",
    price_cents=1234, currency="USD", observed_at=NOW, shipping_cents=400,
)
UNMATCHED = RawListing(
    external_id="listing-2",
    title="Elestrals promotional sticker sheet",
    url="https://fake.test/item/2",
    price_cents=500, currency="USD", observed_at=NOW,
)
GRADED = RawListing(
    external_id="listing-3",
    title="Elestrals Vipyro FE01 012/126 PSA 10 Gem Mint",
    url="https://fake.test/item/3",
    price_cents=25000, currency="USD", observed_at=NOW,
)


class FakeSource:
    """Answers each query from a queue of batches, then goes quiet.

    A fake returning the same listings for every planned query would still produce correct counts
    — the dedupe keys guarantee it — but it would hide which of the two mechanisms was doing the
    work.
    """

    name = "fake"

    def __init__(self, *, reports_sold: bool = False) -> None:
        self.batches: list[list[RawListing]] = []
        self.states: list[ListingState] = []
        self.rechecked: list[str] = []
        self.refuse_after: int | None = None
        self.queries_asked = 0
        self.reports_sold = reports_sold
        self.bound = None

    def describe(self) -> HarvestDescriptor:
        return HarvestDescriptor(
            name=self.name, display_name="Fake source", host=HOST,
            access_mode="scrape", reports_sold=self.reports_sold, expects="text",
        )

    def bind(self, client) -> None:
        self.bound = client

    def discover(self, query, *, limit):
        self.queries_asked += 1
        if self.refuse_after is not None and self.queries_asked > self.refuse_after:
            raise SourceRefused("HTTP 403: the source is refusing us")
        return self.batches.pop(0) if self.batches else []

    def recheck(self, external_ids):
        self.rechecked.extend(external_ids)
        return self.states


class _NullClient:
    def close(self) -> None:
        pass


@pytest.fixture()
def adapter():
    source = FakeSource()
    register("fake", lambda: source)
    try:
        yield source
    finally:
        SOURCES.pop("fake", None)


@pytest.fixture()
def runner(db):
    return HarvestRunner(
        sources=PriceSourceRepository(db),
        harvest=HarvestRepository(db),
        catalog=CatalogSnapshotRepository(db),
        gate=HarvestGate(allowed_hosts=frozenset({HOST}), contact_email="ops@example.com"),
        policy=QuarantinePolicy(threshold=3, base_minutes=60, backoff_factor=4.0,
                                max_minutes=2880),
        client_factory=lambda descriptor, row: _NullClient(),
    )


def listings(db) -> list[MarketListing]:
    return list(db.query(MarketListing).order_by(MarketListing.external_id))


def observations(db) -> list[PriceObservation]:
    return list(db.query(PriceObservation).order_by(PriceObservation.external_id))


def _age(db, listing: MarketListing, *, hours: float) -> None:
    listing.last_seen_at = datetime.now(timezone.utc) - timedelta(hours=hours)
    db.commit()


# --- deep ------------------------------------------------------------------------------

def test_a_deep_scan_records_every_listing_and_prices_only_what_it_could_place(
    db, catalog_rows, source, adapter, runner
):
    adapter.batches = [[MATCHED, UNMATCHED, GRADED]]

    run = runner.run(source_key="fake", mode="deep")

    assert run.status == "success"
    assert run.discovered == 3, "all three are leads worth keeping"
    assert run.accepted == 1, "only the one that placed above the floor becomes a price"
    assert run.rejected == 2

    stored = listings(db)
    assert [row.external_id for row in stored] == ["listing-1", "listing-2", "listing-3"]
    assert stored[0].printing_id == "p-foil"
    assert stored[1].printing_id is None and "no catalog card" in stored[1].match_note
    assert "graded" in stored[2].match_note

    prices = observations(db)
    assert len(prices) == 1
    assert prices[0].sale_type == "listed", "an active listing is an asking price, not a sale"
    assert prices[0].price_cents == 1234


def test_a_second_deep_scan_over_unchanged_results_writes_nothing_new(
    db, catalog_rows, source, adapter, runner
):
    """Idempotency, from the two dedupe keys: `uq_market_listings_source_external` for the
    listing and `uq_price_observations_source_external` for the price."""
    adapter.batches = [[MATCHED, UNMATCHED, GRADED]]
    runner.run(source_key="fake", mode="deep")
    before = len(listings(db)), len(observations(db))

    adapter.batches = [[MATCHED, UNMATCHED, GRADED]]
    second = runner.run(source_key="fake", mode="deep")

    assert second.discovered == 0
    assert second.accepted == 0
    assert (len(listings(db)), len(observations(db))) == before


def test_an_empty_catalog_fails_the_run_loudly(db, source, adapter, runner):
    """ADR-001 left the seed incomplete, so this is reachable — and a deep plan built from an
    empty catalog is a handful of generic sweeps, which looks like a thin success."""
    run = runner.run(source_key="fake", mode="deep")

    assert run.status != "success"
    assert "catalog is empty" in run.error_summary


def test_a_failing_query_does_not_fail_the_run(db, catalog_rows, source, adapter, runner):
    class Exploding(FakeSource):
        def discover(self, query, *, limit):
            if query.reason == "brand sweep":
                raise RuntimeError("upstream 500")
            return super().discover(query, limit=limit)

    exploding = Exploding()
    exploding.batches = [[MATCHED]]
    register("fake", lambda: exploding)

    run = runner.run(source_key="fake", mode="deep")

    assert run.status == "partial", "380 of 400 answers is not a failed run"
    assert "upstream 500" in run.error_summary
    assert run.fetched == 1


# --- light -----------------------------------------------------------------------------

def test_a_light_scan_rechecks_known_listings_and_refreshes_the_asking_price(
    db, catalog_rows, source, adapter, runner
):
    adapter.batches = [[MATCHED]]
    runner.run(source_key="fake", mode="deep")
    known = listings(db)[0]
    _age(db, known, hours=48)

    tomorrow = NOW + timedelta(days=1)
    adapter.states = [ListingState(
        external_id="listing-1", status="active", price_cents=1500, currency="USD",
        observed_at=tomorrow,
    )]
    run = runner.run(source_key="fake", mode="light")

    assert adapter.rechecked == ["listing-1"]
    db.refresh(known)
    assert known.status == "active" and known.price_cents == 1500
    prices = observations(db)
    assert len(prices) == 2, "a new day is a new point, not an overwrite"
    assert {p.price_cents for p in prices} == {1234, 1500}
    assert run.status == "success"


def test_a_listing_that_disappeared_is_ended_but_never_sold(
    db, catalog_rows, source, adapter, runner
):
    """The whole reason `ended_unknown` exists. A listing that vanished may have sold, expired,
    been cancelled or been relisted — and only one of those is a sale."""
    adapter.batches = [[MATCHED]]
    runner.run(source_key="fake", mode="deep")
    known = listings(db)[0]
    _age(db, known, hours=48)

    adapter.states = [ListingState(external_id="listing-1", status="ended_unknown")]
    run = runner.run(source_key="fake", mode="light")

    db.refresh(known)
    assert known.status == "ended_unknown"
    assert known.ended_at is not None
    assert run.ended == 1
    assert not [p for p in observations(db) if p.sale_type == "sold"]


def test_a_source_that_does_not_report_sales_cannot_end_a_listing_as_sold(
    db, catalog_rows, source, adapter, runner
):
    """Even when the connector says so. The check is against `price_sources.reports_sold`, not
    against the connector's word, so a wrong connector cannot manufacture a sale."""
    adapter.batches = [[MATCHED]]
    runner.run(source_key="fake", mode="deep")
    known = listings(db)[0]
    _age(db, known, hours=48)

    adapter.states = [ListingState(
        external_id="listing-1", status="ended_sold", sold_price_cents=9999,
    )]
    runner.run(source_key="fake", mode="light")

    db.refresh(known)
    assert known.status == "ended_unknown", "downgraded — this source cannot report sales"
    assert known.sold_price_cents is None
    assert not [p for p in observations(db) if p.sale_type == "sold"]


def test_a_source_that_does_report_sales_records_the_sale(
    db, catalog_rows, source, adapter, runner
):
    """The same path, with the one column that makes a sale believable set to true. This is what
    ADR-004 bought: a real sale price, at a real sale date."""
    adapter.batches = [[MATCHED]]
    runner.run(source_key="fake", mode="deep")
    known = listings(db)[0]
    _age(db, known, hours=48)

    source.reports_sold = True
    db.commit()
    adapter.states = [ListingState(
        external_id="listing-1", status="ended_sold", sold_price_cents=9999,
    )]
    runner.run(source_key="fake", mode="light")

    db.refresh(known)
    assert known.status == "ended_sold"
    assert known.sold_price_cents == 9999
    sold = [p for p in observations(db) if p.sale_type == "sold"]
    assert len(sold) == 1 and sold[0].price_cents == 9999


def test_a_light_scan_does_not_re_ask_the_whole_catalog(
    db, catalog_rows, source, adapter, runner
):
    """The cheap/expensive distinction between the modes, asserted rather than assumed."""
    deep = runner.run(source_key="fake", mode="deep")
    light = runner.run(source_key="fake", mode="light")

    assert light.queries < deep.queries


def test_a_relisted_item_comes_back_without_an_end_date_in_its_own_past(
    db, catalog_rows, source, adapter, runner
):
    adapter.batches = [[MATCHED]]
    runner.run(source_key="fake", mode="deep")
    known = listings(db)[0]
    _age(db, known, hours=48)
    adapter.states = [ListingState(external_id="listing-1", status="ended_unknown")]
    runner.run(source_key="fake", mode="light")

    adapter.batches = [[MATCHED]]
    runner.run(source_key="fake", mode="deep")

    db.refresh(known)
    assert known.status == "active"
    assert known.ended_at is None


# --- blocks (FR-18) ----------------------------------------------------------------------

def test_sustained_refusals_quarantine_the_source(db, catalog_rows, source, adapter, runner):
    """Under ADR-004 a block is an operating condition. Meeting the first 403 with 399 more
    requests is how a temporary block becomes a permanent one."""
    adapter.refuse_after = 0

    run = runner.run(source_key="fake", mode="deep")

    db.refresh(source)
    assert source.quarantined_until is not None
    assert source.quarantine_level == 1
    assert "refusals" in (source.quarantine_reason or "")
    assert run.status in ("partial", "failed")


def test_the_scan_halts_rather_than_working_through_the_rest_of_the_plan(
    db, catalog_rows, source, adapter, runner
):
    adapter.refuse_after = 0

    runner.run(source_key="fake", mode="deep")

    # The policy threshold is 3 in this fixture; the scan should stop at it rather than asking
    # every one of the planned queries.
    assert adapter.queries_asked == 3


def test_a_quarantined_source_is_refused_on_the_next_run(
    db, catalog_rows, source, adapter, runner
):
    from app.harvest.gate import SourceNotCleared

    adapter.refuse_after = 0
    runner.run(source_key="fake", mode="deep")

    with pytest.raises(SourceNotCleared, match="quarantined"):
        runner.run(source_key="fake", mode="deep")


def test_a_clean_run_clears_the_escalation(db, catalog_rows, source, adapter, runner):
    """A source that recovers must not start its next quarantine at sixteen hours."""
    source.quarantine_level = 2
    db.commit()
    adapter.batches = [[MATCHED]]

    runner.run(source_key="fake", mode="deep")

    db.refresh(source)
    assert source.quarantine_level == 0
    assert source.quarantined_until is None


# --- stopping (story 027) -----------------------------------------------------------------

def test_an_admin_stop_ends_the_run_partial_with_what_it_had(
    db, catalog_rows, source, adapter, runner
):
    """Not `failed`: stopping is a decision, and the data collected before it is real."""
    harvest = HarvestRepository(db)
    run = harvest.start_run(source.id, "deep", triggered_by="admin")
    harvest.request_stop(run)

    result = runner.run(source_key="fake", mode="deep", run=run)

    assert result.status == "partial"
    assert "stopped by an admin" in result.error_summary
    assert adapter.queries_asked == 0, "stopped before the first query"


# --- runs ----------------------------------------------------------------------------------

def test_a_run_left_running_is_swept_to_failed(db, source):
    """FR-2: a crashed run must not sit `running` forever, making "did last night's scan
    finish?" unanswerable."""
    harvest = HarvestRepository(db)
    run = harvest.start_run(source.id, "deep")
    run.started_at = datetime.now(timezone.utc) - timedelta(hours=9)
    db.commit()

    swept = harvest.sweep_stale(older_than_minutes=300)

    db.refresh(run)
    assert swept == 1
    assert run.status == "failed"
    assert "swept" in run.error_summary
