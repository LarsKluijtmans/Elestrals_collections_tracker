"""eBay Browse API — live asking prices, obtained the way eBay says to obtain them.

ADR-003 mapped the routes and this is the one that was open without an approval queue:

    Browse                  open, application-token access, **active listings only**   ← here
    Marketplace Insights    the sold-history API — a Limited Release, "restricted and
                            not open to new users at this time"

ADR-004 then decided to scrape completed listings for the sold data this API cannot give
(`ebay_sold.py`). This connector is kept anyway, and not as a consolation prize: it is free,
published, needs no approval, and asking prices are worth having as long as they are labelled as
asking prices. Between them the two connectors cover both halves of FR-4 from one marketplace,
one of them within its terms and one of them knowingly not.

So this connector reports what is **for sale**, never what **sold**. `reports_sold` is False and
the runner enforces what that means: when a listing we were tracking disappears, this source
cannot tell us whether it sold, expired, or was cancelled, and the listing is recorded as
`ended_unknown` with no sale written. Treating those disappearances as sales would generate a
sales history out of nothing — and FR-4 builds every valuation on `sold`.

Auth is OAuth2 client credentials: a Basic-auth POST for an application token, cached until
just before it expires. No user consent, no user data, no eBay account of anyone else's.

Set EBAY_CLIENT_ID / EBAY_CLIENT_SECRET from a keyset at developer.ebay.com. Sandbox keys work
against `EBAY_ENVIRONMENT=sandbox` and return sandbox inventory, which is a good way to test
the plumbing and a bad way to test the matcher — sandbox titles are not real listings.
"""
from __future__ import annotations

import base64
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from ...config import settings
from ..canonical import HarvestDescriptor, ListingState, Query, RawListing, to_cents
from ..http import PoliteClient, SourceUnavailable
from . import SourceNotConfigured

#: eBay caps `limit` at 200 per page for item_summary/search.
PAGE_MAX = 200

_HOSTS = {
    "production": "api.ebay.com",
    "sandbox": "api.sandbox.ebay.com",
}

#: The public-data scope. Browse needs nothing wider, and asking for wider scopes on a
#: client-credentials token is how a key ends up with permissions nobody audited.
_SCOPE = "https://api.ebay.com/oauth/api_scope"


class EbayBrowseAdapter:
    name = "ebay_browse"

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        environment: str | None = None,
        marketplace_id: str | None = None,
        category_ids: str | None = None,
    ) -> None:
        self._client_id = client_id if client_id is not None else settings.ebay_client_id
        self._client_secret = (
            client_secret if client_secret is not None else settings.ebay_client_secret
        )
        self._environment = (environment or settings.ebay_environment).lower()
        self._marketplace_id = marketplace_id or settings.ebay_marketplace_id
        self._category_ids = (
            category_ids if category_ids is not None else settings.ebay_category_ids
        )
        self._client: PoliteClient | None = None
        self._token: str | None = None
        self._token_expires_at = datetime.min.replace(tzinfo=timezone.utc)

    # --- port ----------------------------------------------------------------------

    def describe(self) -> HarvestDescriptor:
        return HarvestDescriptor(
            name=self.name,
            display_name="eBay Browse API",
            host=_HOSTS.get(self._environment, _HOSTS["production"]),
            access_mode="official_api",
            # The single most consequential line in this file. See the module docstring.
            reports_sold=False,
            terms_url="https://developer.ebay.com/api-docs/static/ebay-rest-landing.html",
            supports_recheck=True,
        )

    def bind(self, client: PoliteClient) -> None:
        """The runner injects the client so the rate limit comes from config, not from here."""
        self._client = client

    def discover(self, query: Query, *, limit: int) -> Iterable[RawListing]:
        """Page through `item_summary/search` until `limit` items or the results run out."""
        client = self._require_client()
        collected: list[RawListing] = []
        offset = 0

        while len(collected) < limit:
            page_size = min(PAGE_MAX, limit - len(collected))
            params: dict[str, object] = {
                "q": query.text,
                "limit": page_size,
                "offset": offset,
            }
            scope = query.scope or self._category_ids
            if scope:
                params["category_ids"] = scope
            if settings.ebay_filter:
                params["filter"] = settings.ebay_filter

            payload = client.get_json(
                "/buy/browse/v1/item_summary/search",
                params=params,
                headers=self._headers(),
            ) or {}

            summaries = payload.get("itemSummaries") or []
            for summary in summaries:
                listing = self._to_listing(summary)
                if listing is not None:
                    collected.append(listing)

            total = int(payload.get("total") or 0)
            offset += page_size
            # Stop on a short page as well as on `total`: a filtered page can come back
            # smaller than requested while `total` still counts the unfiltered set.
            if len(summaries) < page_size or offset >= total:
                break

        return collected

    def recheck(self, external_ids: Sequence[str]) -> Iterable[ListingState]:
        """One `getItem` per listing. A 404 is the answer, not an error.

        Note what is *not* claimed here: `ended_unknown`, never `ended_sold`. eBay's Browse API
        does not report sales, so neither do we.
        """
        client = self._require_client()
        states: list[ListingState] = []
        now = datetime.now(timezone.utc)

        for external_id in external_ids:
            path = f"/buy/browse/v1/item/{quote(external_id, safe='')}"
            try:
                payload = client.get_json(path, headers=self._headers(), not_found_ok=True)
            except SourceUnavailable:
                # Could not read it — which is not the same as "it is gone". Say nothing about
                # this listing rather than ending it on the strength of a 503.
                continue

            if payload is None:
                states.append(
                    ListingState(external_id=external_id, status="ended_unknown", observed_at=now)
                )
                continue

            price = (payload.get("price") or {})
            states.append(ListingState(
                external_id=external_id,
                status="active",
                price_cents=to_cents(price.get("value")),
                currency=price.get("currency"),
                observed_at=now,
            ))

        return states

    # --- internals -----------------------------------------------------------------

    def _require_client(self) -> PoliteClient:
        if self._client is None:
            raise SourceNotConfigured(
                "eBay adapter used before `bind()`. The runner injects the HTTP client so the "
                "rate limit comes from `price_sources.rate_limit_per_min`."
            )
        if not self._client_id or not self._client_secret:
            raise SourceNotConfigured(
                "EBAY_CLIENT_ID / EBAY_CLIENT_SECRET are not set. Create a keyset at "
                "developer.ebay.com; Browse needs only the application (client-credentials) "
                "token, not a user token."
            )
        return self._client

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._application_token()}",
            "X-EBAY-C-MARKETPLACE-ID": self._marketplace_id,
        }

    def _application_token(self) -> str:
        """Cached until 60s before expiry — a token that expires mid-page costs a whole page."""
        now = datetime.now(timezone.utc)
        if self._token and now < self._token_expires_at:
            return self._token

        client = self._require_client()
        basic = base64.b64encode(
            f"{self._client_id}:{self._client_secret}".encode()
        ).decode()
        payload = client.post_json(
            "/identity/v1/oauth2/token",
            data={"grant_type": "client_credentials", "scope": _SCOPE},
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        token = payload.get("access_token")
        if not token:
            raise SourceNotConfigured(
                "eBay returned no access_token. Check the keyset matches EBAY_ENVIRONMENT — "
                "sandbox credentials against the production host fail exactly like this."
            )
        self._token = token
        self._token_expires_at = now + timedelta(
            seconds=max(60, int(payload.get("expires_in") or 7200)) - 60
        )
        return token

    @staticmethod
    def _to_listing(summary: dict) -> RawListing | None:
        """Map one `itemSummary`. Returns None for a row we cannot price.

        A summary with no usable price is dropped rather than defaulted to zero: a zero-priced
        observation is not a cheap card, it is a wrong one, and it drags every median it
        touches.
        """
        external_id = summary.get("itemId")
        price_cents = to_cents((summary.get("price") or {}).get("value"))
        currency = (summary.get("price") or {}).get("currency")
        if not external_id or price_cents is None or not currency:
            return None

        shipping = None
        options = summary.get("shippingOptions") or []
        if options:
            shipping = to_cents((options[0].get("shippingCost") or {}).get("value"))

        return RawListing(
            external_id=str(external_id),
            title=str(summary.get("title") or "").strip(),
            url=str(summary.get("itemWebUrl") or ""),
            price_cents=price_cents,
            currency=str(currency),
            # Now, deliberately: this is what is being asked *at the moment we looked*. The
            # listing's own start date would date the price to before every edit since.
            observed_at=datetime.now(timezone.utc),
            shipping_cents=shipping,
            buying_format=_buying_format(summary.get("buyingOptions") or []),
            image_url=(summary.get("image") or {}).get("imageUrl"),
            location_country=(summary.get("itemLocation") or {}).get("country"),
            # Browse returns active listings. There is no sold flag to read, and inventing one
            # is the failure this whole module is arranged to prevent.
            is_sold=False,
        )


def _buying_format(options: list[str]) -> str:
    """Auction wins the label when an item is both.

    A hybrid listing's `price` is the current bid, not an asking price, and calling that
    `fixed` would feed a rising number into the same series as a stable one.
    """
    upper = {str(option).upper() for option in options}
    if "AUCTION" in upper:
        return "auction"
    if "FIXED_PRICE" in upper:
        return "fixed"
    if "BEST_OFFER" in upper:
        return "best_offer"
    return "unknown"
