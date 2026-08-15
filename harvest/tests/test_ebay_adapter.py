"""The eBay Browse mapping, against a stubbed transport.

No network: `httpx.MockTransport` answers the three endpoints the adapter uses. What is worth
testing here is the mapping and the refusals, because those are where a quiet mistake becomes
a wrong number rather than an error — a price parsed through a float, an auction's current bid
recorded as an asking price, or a 404 read as anything other than "this listing is gone".
"""
from __future__ import annotations

import httpx
import pytest

from app.harvest.http import PoliteClient
from app.harvest.rate_limit import TokenBucket
from app.harvest.sources.ebay_browse import EbayBrowseAdapter
from app.harvest.canonical import Query

SUMMARY = {
    "itemId": "v1|123|0",
    "title": "Elestrals Vipyro FE01 012/126 Holo",
    "itemWebUrl": "https://www.ebay.com/itm/123",
    "price": {"value": "12.34", "currency": "USD"},
    "shippingOptions": [{"shippingCost": {"value": "4.00", "currency": "USD"}}],
    "buyingOptions": ["FIXED_PRICE", "BEST_OFFER"],
    "image": {"imageUrl": "https://i.ebayimg.com/1.jpg"},
    "itemLocation": {"country": "US"},
}


def _bucket() -> TokenBucket:
    """No real waiting, and no real clock — the pacing is tested in `test_harvest_http.py`."""
    return TokenBucket(per_minute=6000, sleep=lambda _: None)


@pytest.fixture()
def transport_log() -> list[str]:
    return []


def build(handler, log) -> EbayBrowseAdapter:
    def wrapped(request: httpx.Request) -> httpx.Response:
        log.append(request.url.path)
        return handler(request)

    adapter = EbayBrowseAdapter(
        client_id="id", client_secret="secret", environment="production",
        marketplace_id="EBAY_US", category_ids="",
    )
    adapter.bind(PoliteClient(
        host="api.ebay.com",
        user_agent="elestral-vault-harvester/1.0 (+ops@example.com)",
        bucket=_bucket(),
        client=httpx.Client(transport=httpx.MockTransport(wrapped), follow_redirects=False),
        sleep=lambda _: None,
    ))
    return adapter


def token_response() -> httpx.Response:
    return httpx.Response(200, json={"access_token": "tok", "expires_in": 7200})


def test_a_summary_maps_to_a_listing_with_money_in_cents(transport_log):
    def handler(request):
        if "oauth2/token" in request.url.path:
            return token_response()
        return httpx.Response(200, json={"total": 1, "itemSummaries": [SUMMARY]})

    adapter = build(handler, transport_log)
    [listing] = list(adapter.discover(Query(text="elestrals", reason="test"), limit=10))

    assert listing.external_id == "v1|123|0"
    assert listing.price_cents == 1234, "12.34 through Decimal, never float arithmetic"
    assert listing.shipping_cents == 400
    assert listing.currency == "USD"
    assert listing.location_country == "US"
    assert listing.buying_format == "fixed"
    assert listing.is_sold is False, "Browse returns active listings; there is no sold flag"


def test_an_auction_is_labelled_an_auction(transport_log):
    """A hybrid listing's price is the current bid. Filing that under `fixed` would feed a
    rising number into the same series as a stable one."""
    def handler(request):
        if "oauth2/token" in request.url.path:
            return token_response()
        summary = dict(SUMMARY, buyingOptions=["AUCTION", "FIXED_PRICE"])
        return httpx.Response(200, json={"total": 1, "itemSummaries": [summary]})

    adapter = build(handler, transport_log)
    [listing] = list(adapter.discover(Query(text="elestrals", reason="test"), limit=10))

    assert listing.buying_format == "auction"


def test_a_summary_with_no_usable_price_is_dropped(transport_log):
    """Not defaulted to zero. A zero-priced observation is not a cheap card, it is a wrong
    one, and it drags every median it touches."""
    def handler(request):
        if "oauth2/token" in request.url.path:
            return token_response()
        broken = dict(SUMMARY)
        broken.pop("price")
        return httpx.Response(200, json={"total": 1, "itemSummaries": [broken]})

    adapter = build(handler, transport_log)
    assert list(adapter.discover(Query(text="elestrals", reason="test"), limit=10)) == []


def test_the_application_token_is_fetched_once_and_reused(transport_log):
    def handler(request):
        if "oauth2/token" in request.url.path:
            return token_response()
        return httpx.Response(200, json={"total": 1, "itemSummaries": [SUMMARY]})

    adapter = build(handler, transport_log)
    adapter.discover(Query(text="a", reason="test"), limit=1)
    adapter.discover(Query(text="b", reason="test"), limit=1)

    assert transport_log.count("/identity/v1/oauth2/token") == 1


def test_paging_stops_on_a_short_page(transport_log):
    """`total` can count an unfiltered set, so a page smaller than requested is also an end —
    without this the adapter pages forever against a source that keeps saying 'more'."""
    def handler(request):
        if "oauth2/token" in request.url.path:
            return token_response()
        return httpx.Response(200, json={"total": 9999, "itemSummaries": [SUMMARY]})

    adapter = build(handler, transport_log)
    results = list(adapter.discover(Query(text="elestrals", reason="test"), limit=400))

    assert len(results) == 1
    assert transport_log.count("/buy/browse/v1/item_summary/search") == 1


def test_recheck_reads_a_404_as_gone_and_never_as_sold(transport_log):
    def handler(request):
        if "oauth2/token" in request.url.path:
            return token_response()
        if request.url.path.endswith("gone"):
            return httpx.Response(404, json={"errors": [{"errorId": 11001}]})
        return httpx.Response(200, json={"price": {"value": "20.00", "currency": "USD"}})

    adapter = build(handler, transport_log)
    states = {s.external_id: s for s in adapter.recheck(["gone", "alive"])}

    assert states["gone"].status == "ended_unknown"
    assert states["alive"].status == "active"
    assert states["alive"].price_cents == 2000
    assert all(state.status != "ended_sold" for state in states.values())


def test_a_source_outage_leaves_a_listing_alone(transport_log):
    """"I could not read it" is not "it is gone". Ending a listing on the strength of a 503
    would record a market event that never happened."""
    def handler(request):
        if "oauth2/token" in request.url.path:
            return token_response()
        return httpx.Response(503)

    adapter = build(handler, transport_log)
    assert list(adapter.recheck(["listing-1"])) == []
