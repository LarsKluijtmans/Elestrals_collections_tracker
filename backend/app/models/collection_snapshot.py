"""`collection_snapshots` — one row per user per day, written from phase 1 and *read* from phase 2.

This table has an unusual job: **it exists to be old.** Nothing in phase 1 reads it. Its entire
purpose is that on the day the portfolio page ships, the chart is not empty — the history is already
there because the snapshot has been running since launch.

The inception log calls it "cheap insurance taken a year early". Not building it was the one
outcome that plan existed to avoid, and for a while that is exactly what happened: intent 002's
stories 021, 022 and 032 were all recorded `blocked` on a table nobody had written.

**`total_value_cents` is nullable, and the nullability is the point.** Phase 1 has no prices, so it
writes counts and leaves value NULL. Phase 2's nightly valuation back-fills the same rows with that
day's rollups. A zero would be a claim — "this collection was worth nothing on 3 March" — and a
false one; NULL says "not valued", which is true and is what `valuation_confidence = 'none'`
reinforces.

The counts are worth having on their own, incidentally. "You owned 400 cards in March and 900 now"
is a real answer, and it needs no pricing at all.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import TimestampMixin, UuidPrimaryKeyMixin

#: Mirrors `price_daily.confidence` so the two never need translating. `none` is the phase-1
#: state — counted, not valued — and is distinct from `low`, which means "valued badly".
VALUATION_CONFIDENCES = ("none", "low", "medium", "high")


class CollectionSnapshot(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "collection_snapshots"

    user_sub: Mapped[str] = mapped_column(String(36), nullable=False)

    #: The day this describes, not the day it was written. A back-fill for 3 March carries
    #: 3 March, so re-running never shifts history sideways.
    taken_on: Mapped[date] = mapped_column(Date(), nullable=False)

    #: Total copies held — the sum of quantities, not the row count.
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Distinct printings held. Diverges from `item_count` exactly as much as the collection has
    #: duplicates in it, which is itself worth being able to chart.
    distinct_printings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: NULL until phase 2 values it. Never 0 to mean "unknown" — see the module docstring.
    total_value_cents: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    valuation_confidence: Mapped[str] = mapped_column(String(8), nullable=False, default="none")

    __table_args__ = (
        # One row per user per day. What makes the snapshot job safe to run twice, and what lets
        # phase 2's back-fill update in place rather than appending a second version of a day.
        UniqueConstraint("user_sub", "taken_on", name="uq_collection_snapshot_user_day"),
        Index("ix_collection_snapshot_user_day", "user_sub", "taken_on"),
    )
