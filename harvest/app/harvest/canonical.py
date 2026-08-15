"""Value objects at the harvester's boundary.

Same shape of idea as `importer/canonical.py`: the adapter's only job is to emit these, and
nothing downstream ever sees a source-specific dict. That is what keeps "add a source" to one
file, and it is why the matcher and the runner can be tested without a network.

The two modes ask an adapter two different questions:

    deep    `discover(query)`  — "what is out there for this search?"     → RawListing
    light   `recheck(ids)`     — "are these specific offers still live?"  → ListingState

An adapter that can only answer the first is still useful; the runner falls back to
re-discovering by title. An adapter that can answer neither is not a source.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol

#: Below this, a match is a guess and the observation is dropped rather than stored as a
#: low-confidence fact (FR-3). It is a floor on *storing a price against a SKU*, not on
#: keeping the listing: unmatched listings stay in `market_listings` as leads.
CONFIDENCE_FLOOR = Decimal("0.70")


def to_cents(value: str | float | Decimal | None) -> int | None:
    """Money in, integer minor units out. `None` for anything that is not a number.

    Never `float(x) * 100`: 19.99 is not representable in binary and rounds to 1998 often
    enough to matter across a million rows. `Decimal` on the string the source actually sent
    is the only version of this that is arithmetically true.
    """
    if value is None:
        return None
    try:
        amount = Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    return int((amount * 100).quantize(Decimal("1")))


@dataclass(frozen=True, slots=True)
class Query:
    """One question to ask a source, and why we are asking it.

    `reason` is carried into the logs so an operator reading a run can tell a query the deep
    plan generated from the catalog apart from one the light plan generated from a listing we
    already hold. Without it, a 900-query run is an undifferentiated wall.
    """

    text: str
    reason: str
    #: 'single' | 'sealed' | None — what we expect to find, used by the matcher as a prior,
    #: never as a conclusion. A query for a booster box still returns singles.
    kind_hint: str | None = None
    #: Source-specific narrowing (an eBay category id, a TCG API set code). Opaque here.
    scope: str | None = None


@dataclass(frozen=True, slots=True)
class RawListing:
    """One offer as the source described it, before any matching."""

    external_id: str
    title: str
    url: str
    price_cents: int
    currency: str
    observed_at: datetime
    shipping_cents: int | None = None
    quantity: int = 1
    buying_format: str = "unknown"
    image_url: str | None = None
    location_country: str | None = None
    #: True only for a source that reports completed sales. The runner asserts against the
    #: source's `reports_sold` before trusting it, so a buggy connector cannot invent sales.
    is_sold: bool = False
    sold_price_cents: int | None = None

    @property
    def effective_price_cents(self) -> int | None:
        """What this listing is evidence of: the sale price when it sold, else the asking price."""
        return self.sold_price_cents if self.is_sold else self.price_cents


@dataclass(frozen=True, slots=True)
class ListingState:
    """What a light scan learned about one known listing."""

    external_id: str
    #: 'active' | 'ended_sold' | 'ended_unsold' | 'ended_unknown'
    status: str
    price_cents: int | None = None
    currency: str | None = None
    sold_price_cents: int | None = None
    observed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class HarvestDescriptor:
    name: str
    display_name: str
    #: The single host this adapter talks to. Checked against the outbound allowlist before a
    #: run starts — the NFR is "the scraper cannot be steered to arbitrary URLs", and an
    #: adapter declaring its host up front is what makes that checkable rather than hoped for.
    host: str
    #: 'official_api' | 'feed' | 'scrape'. Must equal the configured row's `access_mode`; a
    #: disagreement between code and config is a configuration error, not a tie to break.
    access_mode: str
    #: Whether this source reports completed sales. False for every source we can currently
    #: obtain — see `models/market_listing.py`.
    reports_sold: bool
    terms_url: str | None = None
    #: False when the connector cannot look up a listing by id; the runner then says so in the
    #: run rather than silently verifying nothing.
    supports_recheck: bool = True
    #: "json" or "text". Drives the HTTP layer's `Accept` header and, more importantly, what it
    #: does with a 200 that is not what was asked for: for a JSON connector that is a challenge
    #: page, and treating it as an empty result would report a block as a quiet market.
    expects: str = "json"


@dataclass
class HarvestCounts:
    """Accumulated in memory, written once at terminal status."""

    queries: int = 0
    fetched: int = 0
    parsed: int = 0
    accepted: int = 0
    rejected: int = 0
    discovered: int = 0
    ended: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "queries": self.queries,
            "fetched": self.fetched,
            "parsed": self.parsed,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "discovered": self.discovered,
            "ended": self.ended,
        }


class HarvestSource(Protocol):
    """The port. One implementation per source; registered, never imported ad hoc."""

    name: str

    def describe(self) -> HarvestDescriptor: ...

    def discover(self, query: Query, *, limit: int) -> Iterable[RawListing]: ...

    def recheck(self, external_ids: Sequence[str]) -> Iterable[ListingState]: ...
