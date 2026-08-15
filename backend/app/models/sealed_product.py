"""`sealed_products` — the *product*, never anyone's inventory.

A booster box is a catalog row here; the fact that a user owns three of them belongs to
`sealed_inventory_items` in unit 003. `set_id` is nullable because cross-set bundles exist.
"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import TimestampMixin, UuidPrimaryKeyMixin

SEALED_KINDS = (
    "booster_pack", "booster_box", "starter_deck", "elite_box", "bundle", "case", "other",
)


class SealedProduct(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sealed_products"

    set_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sets.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    contents_note: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str | None] = mapped_column(String(512))
    is_tracked_for_price: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("ix_sealed_products_set", "set_id"),)
