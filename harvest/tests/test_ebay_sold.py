"""The eBay completed-listings connector — parsing, and the two refusals.

Fixture-driven, no network. What is tested here is *our* handling: the mapping, the drops, and
the block detection. What is **not** tested here, and cannot be, is whether the selectors match
the live page — bolt 011's opening spike answers that, and story 010's scheduled drift check is
what re-answers it every week afterwards.

The most valuable test in this file is `test_a_challenge_page_is_a_refusal_not_an_empty_market`.
Everything else protects a number; that one protects the pipeline from making a block worse while
reporting success.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.harvest.http import SourceRefused
from app.harvest.sources.ebay_sold import EbaySoldAdapter, _parse_price, _parse_sold_date

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def adapter() -> EbaySoldAdapter:
    return EbaySoldAdapter(host="www.ebay.com")


@pytest.fixture()
def page() -> str:
    return (FIXTURES / "ebay_sold_page.html").read_text(encoding="utf-8")


def test_a_sold_row_maps_to_a_listing_with_its_real_sale_date(adapter, page):
    """The whole technical argument for ADR-004 in one assertion: a real price at a real date,
    which the licensed aggregator could not supply."""
    listings = adapter.parse(page)
    first = listings[0]

    assert first.external_id == "123456789012"
    assert first.title.startswith("Elestrals Vipyro")
    assert first.price_cents == 1234, "12.34 through Decimal, never float arithmetic"
    assert first.currency == "USD"
    assert first.shipping_cents == 400
    assert first.location_country == "US"
    assert first.is_sold is True
    assert first.sold_price_cents == 1234
    assert first.observed_at == datetime(2026, 8, 12, tzinfo=timezone.utc)


def test_the_sale_date_is_the_sale_date_not_the_scrape_time(adapter, page):
    """`observed_at` is when the sale happened. A backfill stamping its own clock would flatten a
    year of history onto one afternoon."""
    for listing in adapter.parse(page):
        assert listing.observed_at.year == 2026
        assert listing.observed_at < datetime.now(timezone.utc)


def test_currencies_other_than_dollars_survive(adapter, page):
    sealed = adapter.parse(page)[1]

    assert sealed.currency == "GBP"
    assert sealed.price_cents == 8999
    assert sealed.location_country == "GB"


def test_a_price_range_is_dropped(adapter, page):
    """"$5.00 to $20.00" is two prices. Recording either as *the* price is a guess with money
    attached."""
    ids = [listing.external_id for listing in adapter.parse(page)]

    assert "323456789012" not in ids


def test_a_row_with_no_parseable_sale_date_is_dropped(adapter, page):
    """Dropped rather than stamped with today. If eBay changes the date format every row drops,
    the accept rate collapses, and the console says so — which is the loud failure we want."""
    ids = [listing.external_id for listing in adapter.parse(page)]

    assert "423456789012" not in ids


def test_the_promo_row_is_ignored(adapter, page):
    """eBay's "Shop on eBay" filler has no item id, so there is nothing to dedupe or re-check."""
    assert len(adapter.parse(page)) == 2


def test_a_challenge_page_is_a_refusal_not_an_empty_market(adapter):
    """HTTP 200, a plausible page, no results container.

    Reading this as "no results" is the failure that makes a scraped pipeline dangerous: the
    scan reports success, the accept rate looks fine because nothing was parsed, and the next
    scheduled run walks straight back into the block.
    """
    challenge = (FIXTURES / "ebay_challenge_page.html").read_text(encoding="utf-8")

    with pytest.raises(SourceRefused, match="no results container"):
        adapter.parse(challenge)


def test_the_connector_declares_that_it_reports_sales(adapter):
    """The only source in the service allowed to write `sold` rows — and the runner still checks
    this against `price_sources.reports_sold` before believing it."""
    descriptor = adapter.describe()

    assert descriptor.reports_sold is True
    assert descriptor.access_mode == "scrape"
    assert descriptor.expects == "text"
    assert descriptor.supports_recheck is False, "a completed sale does not change"


class TestPriceParsing:
    @pytest.mark.parametrize(("text", "cents", "currency"), [
        ("$12.34", 1234, "USD"),
        ("£89.99", 8999, "GBP"),
        ("€5.00", 500, "EUR"),
        ("$1,234.56", 123456, "USD"),
    ])
    def test_known_currencies(self, text, cents, currency):
        assert _parse_price(text) == (cents, currency)

    @pytest.mark.parametrize("text", ["", "Free postage", "$5.00 to $20.00", "Best offer"])
    def test_no_price_is_no_price(self, text):
        assert _parse_price(text) == (None, None)


class TestSoldDateParsing:
    def test_the_documented_format(self):
        assert _parse_sold_date("Sold  12 Aug 2026") == datetime(
            2026, 8, 12, tzinfo=timezone.utc
        )

    @pytest.mark.parametrize("text", ["", "Sold", "Sold yesterday", "12/08/2026", "Sold 32 Aug 2026"])
    def test_anything_else_is_none(self, text):
        """`None` rather than a best guess. The caller drops the row, which is the behaviour that
        makes a format change visible instead of silently wrong."""
        assert _parse_sold_date(text) is None
