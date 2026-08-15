"""eBay completed listings — the sold data ADR-004 was taken to get.

**This is the connector the whole decision rests on.** ADR-003 proposed a licensed aggregator that
supplies aggregate market prices: no sale count, no sale window, no comparables, which would have
forced FR-2, FR-3 and FR-4 to be weakened before construction. A completed-listings page carries
the actual sale price and the actual sale date, so FR-4 survives intact. That is the technical
argument in ADR-004, and this file is where it is cashed in.

It is also the connector that carries the accepted risk. eBay's terms prohibit this. ADR-004
records that, names a risk owner, and this source cannot run until `risk_accepted_by` is set on
its `price_sources` row — the gate refuses it otherwise.

## What is verified and what is not

The **request shape** is stable and public: `/sch/i.html` with `_nkw` (the query), `LH_Sold=1`
and `LH_Complete=1` (completed sales only), `_ipg` (items per page) and `_pgn` (page number).

The **selectors below are not verified against a live page.** They encode the long-standing
`s-item` structure, but marketplace markup changes without notice and nobody has run this against
production HTML. Bolt 011 opens with a timeboxed spike for exactly this, and story 010's drift
test is what tells you the day it stops being true. `_SELECTORS` is a module-level tuple rather
than inline strings so that fix is one edit in one place.

## Two refusals worth knowing about

* **A page with no results container at all is a block, not an empty market.** Interstitials and
  challenge pages return HTTP 200. Reading one as "nothing matched" would report a block as a
  quiet market — the exact failure story 010 exists to prevent — so it raises `SourceRefused` and
  FR-18's counter sees it.
* **A sale whose date cannot be parsed is dropped, not stamped with today.** `observed_at` is
  when the sale happened; a backfill stamping its own clock flattens a year of history onto one
  afternoon. If the date format changes, every row drops, the accept rate collapses, and the
  console says so — which is the loud failure, and the one we want.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone

from selectolax.parser import HTMLParser

from ...config import settings
from ..canonical import HarvestDescriptor, ListingState, Query, RawListing, to_cents
from ..http import PoliteClient, SourceRefused
from . import SourceNotConfigured

#: Items per page. eBay accepts 60/120/240; the largest is fewest requests for the same data,
#: which is the politeness that survived ADR-004.
PAGE_SIZE = 240
MAX_PAGES = 10

#: Every selector in one place, because these are the thing most likely to need changing and
#: the drift test (story 010) exists to tell you when. Each entry is tried in order.
_SELECTORS = {
    "results": ("ul.srp-results", "div.srp-river-results", "ul.b-list__items_nofooter"),
    "item": ("li.s-item", "li.srp-results__item"),
    "title": ("div.s-item__title span[role=heading]", "div.s-item__title", "h3.s-item__title"),
    "link": ("a.s-item__link",),
    "price": ("span.s-item__price",),
    "sold_date": ("span.s-item__caption--signal", "div.s-item__caption span", "span.POSITIVE"),
    "shipping": ("span.s-item__shipping", "span.s-item__logisticsCost"),
    "image": ("img.s-item__image-img",),
    "location": ("span.s-item__location", "span.s-item__itemLocation"),
}

_CURRENCY_SYMBOLS = {"$": "USD", "£": "GBP", "€": "EUR", "C $": "CAD", "AU $": "AUD"}
_PRICE = re.compile(r"([£$€]|C\s*\$|AU\s*\$)?\s*([\d.,]+)")
_SOLD_DATE = re.compile(r"sold\s+(?:item\s+)?(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})", re.I)
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
)}
#: eBay's item id, the stable part of an item URL: /itm/123456789012
_ITEM_ID = re.compile(r"/itm/(?:[^/]+/)?(\d{9,15})")


class EbaySoldAdapter:
    name = "ebay_sold"

    def __init__(self, host: str | None = None, marketplace: str | None = None) -> None:
        self._host = host or settings.ebay_web_host
        self._marketplace = marketplace or settings.ebay_marketplace_id
        self._client: PoliteClient | None = None

    # --- port ----------------------------------------------------------------------

    def describe(self) -> HarvestDescriptor:
        return HarvestDescriptor(
            name=self.name,
            display_name="eBay completed listings",
            host=self._host,
            access_mode="scrape",
            # The one source in this service that may write `sold` rows. It reports actual
            # transactions with actual dates, which is the whole reason ADR-004 was taken.
            reports_sold=True,
            terms_url="https://www.ebay.com/help/policies/member-behaviour-policies/user-agreement",
            # A sold listing has already ended. There is nothing to re-check, and pretending
            # otherwise would spend a light scan's budget confirming that the past is still past.
            supports_recheck=False,
            expects="text",
        )

    def bind(self, client: PoliteClient) -> None:
        self._client = client

    def discover(self, query: Query, *, limit: int) -> Iterable[RawListing]:
        client = self._require_client()
        collected: list[RawListing] = []

        for page in range(1, MAX_PAGES + 1):
            if len(collected) >= limit:
                break
            html = client.get_text("/sch/i.html", params={
                "_nkw": query.text,
                "LH_Sold": 1,
                "LH_Complete": 1,
                "_ipg": PAGE_SIZE,
                "_pgn": page,
            })
            if not html:
                break

            listings = self.parse(html)
            collected.extend(listings[: limit - len(collected)])
            # A short page is the end of the results. Checked as well as the page cap, because
            # eBay keeps serving pages past the real end with the same shell and no items.
            if len(listings) < PAGE_SIZE // 4:
                break
        return collected

    def recheck(self, external_ids: Sequence[str]) -> Iterable[ListingState]:
        """Nothing to do: a completed sale does not change. Declared unsupported in
        `describe()`, so the runner records that rather than silently verifying nothing."""
        return []

    # --- parsing (the part the spike must confirm) -----------------------------------

    def parse(self, html: str) -> list[RawListing]:
        """Parse one results page. Raises `SourceRefused` if this is not a results page."""
        tree = HTMLParser(html)

        if not _first(tree, _SELECTORS["results"]):
            # See the module docstring: a 200 with no results container is an interstitial or a
            # challenge, and reading it as an empty market is the failure mode this whole
            # subsystem is arranged to avoid.
            raise SourceRefused(
                "eBay returned a page with no results container — an interstitial or challenge "
                "page is the usual cause. Treating it as 'no results' would report a block as a "
                "quiet market."
            )

        out: list[RawListing] = []
        for node in _all(tree, _SELECTORS["item"]):
            listing = self._to_listing(node)
            if listing is not None:
                out.append(listing)
        return out

    def _to_listing(self, node) -> RawListing | None:
        url = _attr(node, _SELECTORS["link"], "href") or ""
        match = _ITEM_ID.search(url)
        title = _text(node, _SELECTORS["title"])
        if not match or not title:
            return None  # the "Shop on eBay" placeholder row, and anything else malformed

        price_cents, currency = _parse_price(_text(node, _SELECTORS["price"]))
        if price_cents is None or currency is None:
            return None  # no price is not a cheap card, it is a wrong one

        sold_at = _parse_sold_date(_text(node, _SELECTORS["sold_date"]))
        if sold_at is None:
            # Dropped rather than stamped with today. A wrong sale date is worse than a missing
            # sale, and a format change shows up as a collapsed accept rate rather than as a
            # year of history flattened onto one afternoon.
            return None

        shipping_cents, _ = _parse_price(_text(node, _SELECTORS["shipping"]))

        return RawListing(
            external_id=match.group(1),
            title=title.strip()[:320],
            url=url.split("?")[0],
            price_cents=price_cents,
            currency=currency,
            observed_at=sold_at,
            shipping_cents=shipping_cents,
            buying_format="unknown",
            image_url=_attr(node, _SELECTORS["image"], "src"),
            location_country=_country(_text(node, _SELECTORS["location"])),
            # The one connector allowed to say this — and the runner still checks it against
            # `price_sources.reports_sold` before believing it.
            is_sold=True,
            sold_price_cents=price_cents,
        )

    def _require_client(self) -> PoliteClient:
        if self._client is None:
            raise SourceNotConfigured(
                "eBay sold connector used before `bind()`. The runner injects the HTTP client so "
                "the rate limit comes from `price_sources.rate_limit_per_min`."
            )
        return self._client


# --- helpers -------------------------------------------------------------------------

def _first(tree, selectors: tuple[str, ...]):
    for selector in selectors:
        node = tree.css_first(selector)
        if node is not None:
            return node
    return None


def _all(tree, selectors: tuple[str, ...]) -> list:
    for selector in selectors:
        nodes = tree.css(selector)
        if nodes:
            return nodes
    return []


def _text(node, selectors: tuple[str, ...]) -> str:
    found = _first(node, selectors)
    return found.text(strip=True) if found is not None else ""


def _attr(node, selectors: tuple[str, ...], name: str) -> str | None:
    found = _first(node, selectors)
    return found.attributes.get(name) if found is not None else None


def _parse_price(text: str) -> tuple[int | None, str | None]:
    """"$12.34" → (1234, "USD"). Free shipping and ranges return no price rather than a guess."""
    if not text or "to" in text.lower():
        return None, None  # a price range is two prices; recording either as the price is wrong
    match = _PRICE.search(text)
    if not match:
        return None, None
    symbol = (match.group(1) or "").replace(" ", "")
    currency = _CURRENCY_SYMBOLS.get(symbol) or _CURRENCY_SYMBOLS.get(f"{symbol[:2]} $")
    if currency is None:
        currency = next(
            (code for sym, code in _CURRENCY_SYMBOLS.items() if sym.strip() == symbol), None
        )
    return to_cents(match.group(2)), currency


def _parse_sold_date(text: str) -> datetime | None:
    """"Sold  12 Aug 2026" → an aware UTC datetime. `None` when it does not parse."""
    match = _SOLD_DATE.search(text or "")
    if not match:
        return None
    month = _MONTHS.get(match.group(2).lower())
    if month is None:
        return None
    try:
        return datetime(
            int(match.group(3)), month, int(match.group(1)), tzinfo=timezone.utc
        )
    except ValueError:
        return None


def _country(text: str) -> str | None:
    """"from United States" → a 2-letter code for the handful we see, else None.

    The item's market, not a person — the same distinction `market_listings.location_country`
    documents. A country we do not recognise is left null rather than guessed.
    """
    if not text:
        return None
    lowered = text.lower()
    for needle, code in (
        ("united states", "US"), ("united kingdom", "GB"), ("germany", "DE"),
        ("netherlands", "NL"), ("canada", "CA"), ("australia", "AU"), ("japan", "JP"),
        ("france", "FR"), ("italy", "IT"), ("spain", "ES"),
    ):
        if needle in lowered:
            return code
    return None
