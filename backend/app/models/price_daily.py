"""`price_daily` — read-only, and the **only** thing this service sees of the harvester.

`harvest-api` owns `elestrals_harvest`. This service holds a `SELECT` grant on exactly this one
table there and no write grant on anything (story 019). Listings, runs, match notes and rejected
rows stay on the other side of the line — they are admin-only, and the boundary is a database
privilege rather than a convention.

That makes this table's shape a **published interface**, and changes to it additive only: the two
services deploy independently, so a removed or repurposed column is an outage in whichever
deploys second.

A grant rather than an API call, deliberately. An HTTP call would make this service depend on the
harvester's availability, which is exactly what FR-13 exists to prevent — a blocked scraper must
degrade freshness, never `/collection`. It would also put a network hop inside the price tab's
p95 < 250ms budget, which a cross-schema read of an indexed table does not.

`settings.harvest_schema` is blank on the SQLite unit-test path, where the table is created
unqualified in the same database.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..config import settings
from ..core.db import Base

CONFIDENCE_LEVELS = ("low", "medium", "high")
#: `sold` is a completed transaction and the only thing valuation may read. `listed` is somebody's
#: asking price: shown, labelled, and `low` confidence by definition.
SALE_TYPES = ("sold", "listed")


class PriceDaily(Base):
    __tablename__ = "price_daily"
    __table_args__ = (
        Index("ix_price_daily_printing_day", "printing_id", "day"),
        {"schema": settings.harvest_schema or None},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    printing_id: Mapped[str | None] = mapped_column(String(36))
    sealed_product_id: Mapped[str | None] = mapped_column(String(36))
    condition: Mapped[str | None] = mapped_column(String(24))
    #: Non-null mirrors of the three above, which the harvester keeps so its unique key has
    #: something without NULLs to hold on to. Read here only when grouping.
    product_key: Mapped[str] = mapped_column(String(36))
    product_kind: Mapped[str] = mapped_column(String(8))
    condition_key: Mapped[str] = mapped_column(String(24))

    day: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3))
    sale_type: Mapped[str] = mapped_column(String(8))

    low_cents: Mapped[int] = mapped_column(BigInteger)
    median_cents: Mapped[int] = mapped_column(BigInteger)
    high_cents: Mapped[int] = mapped_column(BigInteger)
    mean_cents: Mapped[int] = mapped_column(BigInteger)

    observation_count: Mapped[int] = mapped_column(Integer)
    source_count: Mapped[int] = mapped_column(Integer)
    excluded_count: Mapped[int] = mapped_column(Integer)
    #: No monetary figure renders without this. `ConfidencePill` is a required prop on the money
    #: component precisely so a figure without it fails to compile rather than shipping.
    confidence: Mapped[str] = mapped_column(String(8))

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
