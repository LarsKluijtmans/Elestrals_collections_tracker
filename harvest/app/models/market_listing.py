"""`market_listings` — one row per *offer we have seen*, tracked over its whole life.

`price_observations` is a fact log — append-only, one row per price point — and answers "what was
this worth on the 3rd". This table is the mutable other half and answers "is that thing still for
sale?", which a table that only appends can never answer.

Not to be confused with `listings` in `standards/data-model.md`: that is *our* marketplace, where
a row means a user of this site is selling something. This is the outside world, and it has no
`seller_sub`, no seller name and no buyer anything — the NFR is "prices, dates, titles and URLs
only". `location_country` is the one exception and is kept deliberately: the same card in the US
and in the EU is two different prices, so a valuation that mixes them silently is wrong. It
describes the item's market, not a person.

**`printing_id` and `sealed_product_id` are plain columns, not foreign keys.** They point into
`elestrals`, a schema this service cannot write and does not own. A cross-schema FK would make
phase 1 unable to change its own catalog without this service's cooperation, which is exactly the
coupling FR-13 exists to prevent. The cost is that a deleted printing leaves a dangling id here;
the admin explorer shows those as unmatched, which is the honest reading of "the catalog no longer
has this".

## The status machine, and the one lie it refuses to tell

    active          seen live in the most recent scan that looked for it
    ended_sold      the source *told us it sold*
    ended_unsold    the source told us it ended without a sale
    ended_unknown   it was live, now it is gone, and nobody said why

`ended_unknown` is the honest majority case and the reason this enum has four values instead of
two. When a listing disappears from a source that lists only active offers it may have sold,
expired, been cancelled, been relisted, or been hidden from our region. Recording that as a sale
would manufacture a transaction that may never have happened, and FR-4 builds valuation on `sold`.
So the runner may only write `ended_sold` from a source whose `reports_sold` is true, and no
`sold` observation is ever derived from a disappearance.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import TimestampMixin, UuidPrimaryKeyMixin, _utcnow

KINDS = ("single", "sealed", "lot", "unknown")
STATUSES = ("active", "ended_sold", "ended_unsold", "ended_unknown")
ENDED_STATUSES = ("ended_sold", "ended_unsold", "ended_unknown")
BUYING_FORMATS = ("fixed", "auction", "best_offer", "unknown")


class MarketListing(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "market_listings"

    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("price_sources.id", ondelete="CASCADE"), nullable=False
    )
    #: The source's own id for this offer. Half of the dedupe key, and the handle the light scan
    #: re-reads a known listing by.
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)

    title: Mapped[str] = mapped_column(String(320), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(512))

    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")

    # Cross-schema references, deliberately not FKs. See the module docstring.
    printing_id: Mapped[str | None] = mapped_column(String(36))
    sealed_product_id: Mapped[str | None] = mapped_column(String(36))
    condition: Mapped[str | None] = mapped_column(String(24))
    match_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    #: Why it matched, or why it did not. An unmatched listing is a *lead*: either a product
    #: missing from the catalog or a matcher gap, and this string is how an operator tells those
    #: apart without re-running anything.
    match_note: Mapped[str | None] = mapped_column(String(255))

    price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    shipping_cents: Mapped[int | None] = mapped_column(BigInteger)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    buying_format: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")

    #: The item's market, not a person. See the module docstring.
    location_country: Mapped[str | None] = mapped_column(String(2))

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    #: Advanced only when a scan *looked for this listing and found it*. A light scan that
    #: skipped it must not refresh this, or "gone" becomes indistinguishable from "not asked
    #: about since Tuesday" — and the whole light scan is built on that distinction.
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Set only alongside `ended_sold`, and therefore only from a source that reports sales.
    sold_price_cents: Mapped[int | None] = mapped_column(BigInteger)

    first_seen_run_id: Mapped[str | None] = mapped_column(String(36))
    last_seen_run_id: Mapped[str | None] = mapped_column(String(36))

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_market_listings_source_external"),
        # The light scan's driving query: live rows for a source, oldest look-up first.
        Index("ix_market_listings_source_status_seen", "source_id", "status", "last_seen_at"),
        Index("ix_market_listings_printing", "printing_id", "status"),
        Index("ix_market_listings_sealed", "sealed_product_id", "status"),
        # "What could not be matched?" is an operator's first question, and it must not scan.
        Index("ix_market_listings_unmatched", "source_id", "kind", "match_confidence"),
        # The explorer's default view.
        Index("ix_market_listings_seen", "last_seen_at"),
    )
