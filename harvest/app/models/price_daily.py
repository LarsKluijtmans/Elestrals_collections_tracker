"""`price_daily` — the rollup everything reads, and **the entire contract between the services**.

Charts and valuation never scan the fact table. More than that: `price_daily` is the only table
`elestrals-api` is granted to read out of `elestrals_harvest` (story 019). Listings, runs, match
notes and rejections stay on this side of the line.

That makes this table's shape a published interface, and changes to it **additive only**. The two
services deploy independently; a removed or repurposed column is an outage in whichever deploys
second.

**Confidence rule**, from the requirements and enforced here rather than in a chart:

    high    ≥ 5 sold observations from ≥ 2 sources in the window
    medium  ≥ 2 sold observations
    low     anything else, **including anything derived from `listed` prices**

The UI must never show a value without it, and `ConfidencePill` being a required prop is how that
is kept true on the other side.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger, Date, DateTime, Index, Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import UuidPrimaryKeyMixin, _utcnow

CONFIDENCE_LEVELS = ("low", "medium", "high")


class PriceDaily(Base, UuidPrimaryKeyMixin):
    __tablename__ = "price_daily"

    # --- the readable columns --------------------------------------------------------
    # Cross-schema references by id, no FK — the catalog is phase 1's to change.
    printing_id: Mapped[str | None] = mapped_column(String(36))
    sealed_product_id: Mapped[str | None] = mapped_column(String(36))
    #: NULL is a real bucket, not a missing value: a seller who does not state a condition is
    #: disproportionately selling a played card, so folding those into Near Mint biases every
    #: median upward.
    condition: Mapped[str | None] = mapped_column(String(24))

    # --- the key columns -------------------------------------------------------------
    # The same lesson `uq_inventory_merge` records in phase 1: **both MySQL and SQLite treat
    # NULLs as distinct in a unique index**, so a key containing a nullable column does not
    # constrain the rows where it is null. Two of the three natural key parts here are nullable
    # — a sealed rollup has no printing, and an unstated condition is a legitimate bucket — so
    # the constraint would have silently permitted a duplicate row on every re-run, which is
    # exactly what it exists to prevent.
    #
    # These two columns carry the same information with no nulls in it, and the unique key is
    # built from them instead.
    #: The printing id or the sealed product id — whichever this row is about.
    product_key: Mapped[str] = mapped_column(String(36), nullable=False)
    #: 'printing' or 'sealed'. Without it, a printing and a sealed product that somehow shared an
    #: id would collide.
    product_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    #: `condition`, or '' when unstated. The empty string is the *unstated* bucket, and it is a
    #: real one — not a missing value.
    condition_key: Mapped[str] = mapped_column(String(24), nullable=False, default="")

    day: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    #: `sold` and `listed` roll up into separate rows and are never blended. A card can have
    #: both; the UI picks which to show and labels it.
    sale_type: Mapped[str] = mapped_column(String(8), nullable=False)

    low_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    median_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    high_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mean_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)

    #: Counts what was **kept** after outlier exclusion, so confidence is computed on the data
    #: actually used rather than on what was seen.
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: How many points the IQR rule dropped. Shown in the admin distribution view; a day where
    #: this spikes is a broken connector more often than a strange market.
    excluded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    confidence: Mapped[str] = mapped_column(String(8), nullable=False, default="low")

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    __table_args__ = (
        # The rollup recomputes a day in place rather than accumulating, and this is what makes
        # "run it again and get the same answer" true. Built from the non-null key columns — see
        # the comment on `product_key` for why the readable ones cannot be used here.
        UniqueConstraint(
            "product_key", "product_kind", "condition_key", "day", "currency", "sale_type",
            name="uq_price_daily_key",
        ),
        # The price tab's read: one printing, a date range. p95 < 250ms depends on this.
        Index("ix_price_daily_printing_day", "printing_id", "day"),
        Index("ix_price_daily_sealed_day", "sealed_product_id", "day"),
        # Valuation's read: the latest day across many printings at once.
        Index("ix_price_daily_day_type", "day", "sale_type"),
    )
