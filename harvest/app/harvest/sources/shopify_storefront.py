"""Shopify storefronts — the hobby shops, read through the JSON their storefront publishes.

Most independent card shops run Shopify, and every Shopify storefront serves its own product
catalog at `/products.json`. That endpoint is part of the storefront, not a private API: it is
what the shop's own theme and every price-comparison integration reads. Fetching it is a
normal client of a published interface, which is a different act from parsing a page meant for
a browser — and this adapter therefore registers as `official_api`, not `scrape`.

**One shop is one source.** Each configured shop gets its own row in `price_sources`, its own
ToS review note, its own kill switch and its own rate limit. Bundling them behind a single
`shopify` source would put one review note in front of a dozen sets of terms, which is FR-1's
gate defeated by tidiness. Configure them explicitly:

    HARVEST_SHOPIFY_SHOPS=cards.example.com:USD,winkel.example.nl:EUR

The currency is configured rather than detected because `/products.json` does not carry one,
and a price without a currency is not money — standards §3 says reject it at the boundary, so
an unconfigured shop cannot be configured at all.

**One fetch per run.** `/products.json` has no server-side search, so the whole catalog is
fetched once, cached on the adapter (which is per-run), and every query filters it in memory.
A light scan over a shop is therefore one or two HTTP requests, not one per listing.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from ...config import settings
from ..canonical import HarvestDescriptor, ListingState, Query, RawListing, to_cents
from ..http import PoliteClient

#: `price_sources.key` is VARCHAR(32) and the key is the join between config and code.
KEY_MAX = 32
PAGE_SIZE = 250
#: 250 × 20 = 5,000 products. A hobby shop that exceeds this is not the shape of shop this
#: adapter was written for, and silently reading half of one is worse than saying so.
MAX_PAGES = 20


@dataclass(frozen=True, slots=True)
class ShopSpec:
    host: str
    currency: str


def configured_shops() -> list[ShopSpec]:
    """Parse `HARVEST_SHOPIFY_SHOPS`. Malformed entries are skipped, never guessed at."""
    shops: list[ShopSpec] = []
    for entry in settings.harvest_shopify_shops.split(","):
        entry = entry.strip()
        if not entry:
            continue
        host, _, currency = entry.partition(":")
        host, currency = host.strip().lower(), currency.strip().upper()
        if not host or len(currency) != 3:
            continue  # no currency, no source — see the module docstring
        shops.append(ShopSpec(host=host, currency=currency))
    return shops


class ShopifyStorefrontAdapter:
    #: Class attribute for symmetry with the other adapters; instances override it per shop.
    name = "shopify"

    def __init__(self, shop: ShopSpec) -> None:
        self._shop = shop
        self.name = self.name_for(shop)
        self._client: PoliteClient | None = None
        self._products: list[dict] | None = None

    @staticmethod
    def name_for(shop: ShopSpec) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", shop.host.lower()).strip("_")
        return f"shopify_{slug}"[:KEY_MAX]

    # --- port ----------------------------------------------------------------------

    def describe(self) -> HarvestDescriptor:
        return HarvestDescriptor(
            name=self.name,
            display_name=f"Shopify storefront — {self._shop.host}",
            host=self._shop.host,
            access_mode="official_api",
            # A shop showing "sold out" has not told us a sale happened, at what price, or on
            # what day. Same rule as everywhere else: no source claims sales it cannot report.
            reports_sold=False,
            terms_url=f"https://{self._shop.host}/policies/terms-of-service",
            supports_recheck=True,
        )

    def bind(self, client: PoliteClient) -> None:
        self._client = client

    def discover(self, query: Query, *, limit: int) -> Iterable[RawListing]:
        terms = [term for term in _normalise(query.text).split() if len(term) > 2]
        found: list[RawListing] = []

        for product in self._catalog():
            haystack = _normalise(
                f"{product.get('title', '')} {product.get('product_type', '')} "
                f"{' '.join(product.get('tags') or [])}"
            )
            # Every term must appear. A shop's catalog is small enough that an "any term"
            # match returns the whole store for a query containing the word "box".
            if terms and not all(term in haystack for term in terms):
                continue
            for listing in self._to_listings(product):
                found.append(listing)
                if len(found) >= limit:
                    return found
        return found

    def recheck(self, external_ids: Sequence[str]) -> Iterable[ListingState]:
        """Answered from the one catalog fetch — no per-listing request at all.

        Gone from the catalog, or present but unavailable, both land on `ended_unknown`. A
        sold-out variant may have sold or may have been pulled; the storefront does not say,
        so neither do we.
        """
        now = datetime.now(timezone.utc)
        live: dict[str, RawListing] = {}
        for product in self._catalog():
            for listing in self._to_listings(product, include_unavailable=False):
                live[listing.external_id] = listing

        states: list[ListingState] = []
        for external_id in external_ids:
            listing = live.get(external_id)
            if listing is None:
                states.append(
                    ListingState(external_id=external_id, status="ended_unknown", observed_at=now)
                )
            else:
                states.append(ListingState(
                    external_id=external_id,
                    status="active",
                    price_cents=listing.price_cents,
                    currency=listing.currency,
                    observed_at=now,
                ))
        return states

    # --- internals -----------------------------------------------------------------

    def _catalog(self) -> list[dict]:
        """Fetch every page once per run, then serve from memory."""
        if self._products is not None:
            return self._products
        if self._client is None:
            raise RuntimeError(f"{self.name}: used before `bind()`")

        products: list[dict] = []
        for page in range(1, MAX_PAGES + 1):
            payload = self._client.get_json(
                "/products.json", params={"limit": PAGE_SIZE, "page": page}
            ) or {}
            batch = payload.get("products") or []
            products.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
        self._products = products
        return products

    def _to_listings(self, product: dict, *, include_unavailable: bool = True) -> list[RawListing]:
        """One listing per **variant** — the variant is what carries the price.

        A product with a Near Mint and a Lightly Played variant is two offers at two prices,
        and collapsing them onto the product would record one of the prices as both.
        """
        handle = product.get("handle") or ""
        title = str(product.get("title") or "").strip()
        images = product.get("images") or []
        image_url = images[0].get("src") if images else None
        now = datetime.now(timezone.utc)

        listings: list[RawListing] = []
        for variant in product.get("variants") or []:
            available = bool(variant.get("available", True))
            if not available and not include_unavailable:
                continue
            price_cents = to_cents(variant.get("price"))
            if price_cents is None:
                continue

            variant_title = str(variant.get("title") or "").strip()
            # "Default Title" is Shopify's placeholder for a product with no options; joining
            # it onto the title would feed the matcher a phrase no human wrote.
            full_title = (
                f"{title} {variant_title}".strip()
                if variant_title and variant_title.lower() != "default title"
                else title
            )

            listings.append(RawListing(
                external_id=f"{product.get('id')}:{variant.get('id')}",
                title=full_title,
                url=f"https://{self._shop.host}/products/{handle}?variant={variant.get('id')}",
                price_cents=price_cents,
                currency=self._shop.currency,
                observed_at=now,
                buying_format="fixed",
                image_url=image_url,
                is_sold=False,
            ))
        return listings


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
