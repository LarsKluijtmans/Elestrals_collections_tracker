"""`price_observations` — the raw fact table, append-only.

Shaped by `standards/data-model.md`. Three things about it are load-bearing rather than
stylistic:

**`sale_type` is never mixed** (FR-4). `sold` is a completed transaction and the only thing
valuation may read; `listed` is somebody's asking price and may be shown, labelled, at `low`
confidence. The runner will not write `sold` from a source whose `reports_sold` is false, so a
listing that merely vanished cannot become a sale by accident.

**`UNIQUE (source_id, external_id)` is what makes a re-run free** (FR-3). For a `sold` row the
external id is the source's transaction id. For a `listed` row there is no transaction to key on
— the same offer is seen on every scan, at a price that may move — so the runner keys it
`"{listing_id}@{YYYY-MM-DD}"`. That yields at most one asking-price point per listing per day: an
hourly light scan writes one row a day, while tomorrow's price change still lands as its own row.

**`printing_id` and `sealed_product_id` are plain columns, not foreign keys**, for the same
reason as in `market_listing.py`: they point into a schema this service cannot write.

The primary key is a `BIGINT AUTO_INCREMENT`, against the project rule that public ids are UUIDs,
because at the 50M-row NFR target a random 36-char key is a page-split machine. It is legal here
precisely because this id never leaves the backend: the API exposes rollups and, at most, a
listing's `source_url`.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import _utcnow

SALE_TYPES = ("sold", "listed")


class PriceObservation(Base):
    __tablename__ = "price_observations"

    # `.with_variant` keeps the unit-test path honest: SQLite only auto-increments an INTEGER
    # PRIMARY KEY, so a BIGINT one silently stops handing out ids.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )

    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("price_sources.id", ondelete="CASCADE"), nullable=False
    )
    #: Provenance for every row: which run put it here, under which mode, against which plan.
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("harvest_runs.id", ondelete="CASCADE"), nullable=False
    )

    # Exactly one of the two is set. Enforced by the runner, which will not write an observation
    # the matcher could not place.
    printing_id: Mapped[str | None] = mapped_column(String(36))
    sealed_product_id: Mapped[str | None] = mapped_column(String(36))

    condition: Mapped[str | None] = mapped_column(String(24))
    sale_type: Mapped[str] = mapped_column(String(8), nullable=False)

    #: When the sale happened or the price was being asked — *not* when we read it. A backfill
    #: stamping its own clock here flattens a year of history onto one afternoon.
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    shipping_cents: Mapped[int | None] = mapped_column(BigInteger)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    #: Auditable back to origin. Every figure the UI shows traces to a page a human can open,
    #: which under ADR-004 is what makes "we report observed sales" a checkable claim rather
    #: than an assertion.
    source_url: Mapped[str] = mapped_column(String(512), nullable=False)

    match_confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)

    #: Set by the rollup when this point fell beyond 3× IQR. **Flagged, never deleted** — a
    #: silently dropped point is indistinguishable from one that never existed, and the admin
    #: distribution view draws these.
    is_outlier: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: A correction is a new row plus this flag on the old one, never an edit.
    is_excluded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_price_observations_source_external"),
        Index("ix_price_observations_printing_observed", "printing_id", "observed_at"),
        Index("ix_price_observations_sealed_observed", "sealed_product_id", "observed_at"),
        Index("ix_price_observations_run", "run_id"),
        # The rollup's driving scan: one day's rows, by type.
        Index("ix_price_observations_day", "observed_at", "sale_type"),
    )
