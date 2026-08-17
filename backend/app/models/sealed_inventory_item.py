"""`sealed_inventory_items` — sealed product a user owns.

**A separate table from `inventory_items`, and that is the whole design.** Story 025's third
criterion is that sealed holdings appear in neither `/collection` nor any completion figure, and the
cheapest way to guarantee that is for them not to be in the table those queries read. A `kind`
column on one shared table would put the burden on every future query remembering to exclude
sealed — and the one that forgets reports a booster box as a card.

The merge rule mirrors bolt 004's, one layer simpler. Two sealed boxes in the same state merge into
`quantity 2`; a sealed box and an opened one do not, because `is_sealed` is part of the key. That
falls out of the unique constraint rather than out of a service remembering to branch.

**Marking a box opened creates no singles, ever.** The expected distribution is never the actual
pull, so generated cards would be wrong every single time — and wrong in a way the collector has to
hunt down and correct one row at a time. The flag flips; that is all it does.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base
from .base import TimestampMixin, UuidPrimaryKeyMixin


class SealedInventoryItem(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sealed_inventory_items"

    user_sub: Mapped[str] = mapped_column(String(36), nullable=False)
    sealed_product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sealed_products.id", ondelete="RESTRICT"), nullable=False
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    #: One-way by design. A box that has been opened cannot be re-sealed, and modelling a
    #: transition back would invite a UI that offers it.
    is_sealed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    acquired_on: Mapped[date | None] = mapped_column(Date())
    acquired_unit_price_cents: Mapped[int | None] = mapped_column(BigInteger)
    acquired_currency: Mapped[str | None] = mapped_column(String(3))
    storage_location: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(String(512))

    product = relationship("SealedProduct", lazy="selectin")

    __table_args__ = (
        # `is_sealed` is *in* the key: sealed and opened copies of one product are different
        # holdings and must not merge. Bolt 004's merge_condition trick is not needed here
        # because there is no NULL case — every row is one or the other.
        UniqueConstraint(
            "user_sub", "sealed_product_id", "is_sealed", name="uq_sealed_inventory_merge"
        ),
        CheckConstraint("quantity > 0", name="ck_sealed_quantity_positive"),
        Index("ix_sealed_inventory_user", "user_sub"),
    )
