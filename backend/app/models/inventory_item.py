"""`inventory_items` — what a user owns.

Two rules are enforced by the schema rather than by convention, because both fail silently
when they are only enforced in a service:

**1. Ungraded duplicates merge; graded copies do not.**
A second Near Mint copy of a printing should become `quantity 2`, but a second PSA 9 copy is an
individually meaningful object — it has its own serial, its own value, and may be sold
separately. A single UNIQUE over `(user_sub, printing_id, condition, is_graded, grader, grade)`
cannot express that: it would merge two PSA 9 copies into one row.

The discriminator is `merge_condition`: the condition for ungraded rows, and **NULL for graded
ones**. Both MySQL and SQLite treat NULLs as distinct in a UNIQUE index, so every graded copy
gets its own row for free while ungraded copies collide and merge. No service-layer branch can
be forgotten, and no concurrent request can slip between a check and a write.

**2. `user_sub` leads every index.** Ownership is not a filter someone remembers to add.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, ForeignKey, Index, Integer,
    Numeric, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base
from .base import TimestampMixin, UuidPrimaryKeyMixin

CONDITIONS = (
    "mint", "near_mint", "lightly_played", "moderately_played", "heavily_played", "damaged",
)


class InventoryItem(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "inventory_items"

    # The JWT `sub`. Never a client-supplied id.
    user_sub: Mapped[str] = mapped_column(String(36), nullable=False)
    printing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("printings.id", ondelete="RESTRICT"), nullable=False
    )

    condition: Mapped[str] = mapped_column(String(24), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    is_graded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    grader: Mapped[str | None] = mapped_column(String(16))
    grade: Mapped[float | None] = mapped_column(Numeric(3, 1))

    #: The merge discriminator — `condition` when ungraded, NULL when graded. See the module
    #: docstring: this column is the whole reason graded copies stay separate rows.
    merge_condition: Mapped[str | None] = mapped_column(String(24))

    acquired_on: Mapped[date | None] = mapped_column(Date())
    acquired_unit_price_cents: Mapped[int | None] = mapped_column(BigInteger)
    acquired_currency: Mapped[str | None] = mapped_column(String(3))

    storage_location: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(String(512))
    is_for_trade: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    printing = relationship("Printing", lazy="selectin")

    __table_args__ = (
        UniqueConstraint(
            "user_sub", "printing_id", "merge_condition", name="uq_inventory_merge"
        ),
        CheckConstraint("quantity > 0", name="ck_inventory_quantity_positive"),
        Index("ix_inventory_user_printing", "user_sub", "printing_id"),
        Index("ix_inventory_user_created", "user_sub", "created_at"),
    )

    @staticmethod
    def merge_key_for(*, condition: str, is_graded: bool) -> str | None:
        """One place decides what merges. A graded copy has no merge key at all."""
        return None if is_graded else condition
