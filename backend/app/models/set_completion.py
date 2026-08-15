"""`set_completion` — how much of a set a user owns.

A summary table that can drift from its source is worse than no summary table, so this is
recomputed **inside the same transaction as the inventory write**. If the recompute fails, the
write rolls back with it. There is no eventual consistency here to explain to a collector who
just added a card and sees the old number.

`owned_cards` counts distinct **cards** for which the user owns at least one printing, over
`sets.card_count` — the declared printed size. Cards, not printings, because 126 cards can
carry 189 printings and a percentage over the wrong denominator reads above 100%.

Note the deliberate vocabulary split: *coverage* is how much of a set our catalog holds;
*completion* is how much of it a person owns. Conflating them is how "you own 100%" appears
for a set we only half-imported.
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import TimestampMixin, UuidPrimaryKeyMixin


class SetCompletion(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "set_completion"

    user_sub: Mapped[str] = mapped_column(String(36), nullable=False)
    set_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sets.id", ondelete="CASCADE"), nullable=False
    )

    #: Distinct cards in the set for which the user owns >= 1 printing.
    owned_cards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: The declared printed size, copied at recompute so the ratio is self-contained.
    card_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Total copies held in the set — the "142 copies across 98 cards" number.
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("user_sub", "set_id", name="uq_set_completion_user_set"),
        Index("ix_set_completion_user", "user_sub"),
    )
