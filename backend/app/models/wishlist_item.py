"""`wishlist_items` — printings a collector wants.

Two rules, both from story 026, and both enforced here rather than in a service.

**A printing cannot be wished twice.** `uq_wishlist_user_printing` says so, so no concurrent
double-submit can produce two rows.

**Money is never a bare number.** `max_price_cents` and `max_price_currency` travel together: a
maximum of "500" is meaningless without knowing whether that is euros or yen, and the story rejects
it outright. The CHECK enforces the pair, so a caller cannot set one without the other — the same
reasoning `acquired_unit_price_cents` follows in `inventory_items`.

What is *not* here is any automatic clearing. Acquiring a wished printing prompts; it does not
silently remove the wish. A collector may want a second copy, or a better condition, and deleting
their stated intent because a row appeared elsewhere loses information they cannot get back.

These rows are also the seed for phase-2 price alerts. The schema anticipates that — `max_price_cents`
is exactly the threshold an alert would fire on — without building it.
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base
from .base import TimestampMixin, UuidPrimaryKeyMixin

PRIORITIES = ("low", "normal", "high")


class WishlistItem(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "wishlist_items"

    user_sub: Mapped[str] = mapped_column(String(36), nullable=False)
    printing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("printings.id", ondelete="CASCADE"), nullable=False
    )

    desired_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    priority: Mapped[str] = mapped_column(String(8), nullable=False, default="normal")

    #: Optional, but never half-set. See the CHECK below.
    max_price_cents: Mapped[int | None] = mapped_column(BigInteger)
    max_price_currency: Mapped[str | None] = mapped_column(String(3))

    notes: Mapped[str | None] = mapped_column(String(512))

    printing = relationship("Printing", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("user_sub", "printing_id", name="uq_wishlist_user_printing"),
        CheckConstraint("desired_quantity > 0", name="ck_wishlist_quantity_positive"),
        # Both or neither. A bare number is not money, and half a price is worse than no price
        # because it looks like one.
        CheckConstraint(
            "(max_price_cents IS NULL AND max_price_currency IS NULL) "
            "OR (max_price_cents IS NOT NULL AND max_price_currency IS NOT NULL)",
            name="ck_wishlist_price_is_money",
        ),
        Index("ix_wishlist_user", "user_sub"),
    )
