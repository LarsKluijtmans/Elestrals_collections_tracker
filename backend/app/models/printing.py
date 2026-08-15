"""`printings` — **the SKU**.

The thing a collector actually owns, a price attaches to, and a listing sells. Inventory,
price observations, wishlists and listings all point here, never at `cards`.

The UNIQUE over the natural key is not decoration: it is what makes the importer's upsert
idempotent under *concurrency*, not merely in sequence.
"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base
from .base import TimestampMixin, UuidPrimaryKeyMixin

RARITIES = (
    "common", "uncommon", "rare", "holo_rare", "full_art",
    "alt_art", "prismatic", "secret", "promo",
)
FINISHES = ("normal", "foil", "reverse_foil", "prismatic")
EDITIONS = ("unlimited", "first")


class Printing(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "printings"

    card_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cards.id", ondelete="CASCADE"), nullable=False
    )

    rarity: Mapped[str] = mapped_column(String(16), nullable=False)
    finish: Mapped[str] = mapped_column(String(16), nullable=False)
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="en")
    edition: Mapped[str] = mapped_column(String(16), nullable=False, default="unlimited")

    # A URL, never bytes — until written permission exists. See adr-001 and the brief's
    # trademark risk.
    image_url: Mapped[str | None] = mapped_column(String(512))

    # Lets phase 2 stop scraping dead SKUs without deleting catalog history.
    is_tracked_for_price: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    card = relationship("Card", back_populates="printings")

    __table_args__ = (
        UniqueConstraint(
            "card_id", "rarity", "finish", "language", "edition", name="uq_printings_natural_key"
        ),
        Index("ix_printings_card", "card_id"),
        Index("ix_printings_tracked", "is_tracked_for_price"),
    )
