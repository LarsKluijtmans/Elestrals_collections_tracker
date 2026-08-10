"""`cards` — a named card, independent of how it was printed.

A collector does not own "Vipyro"; they own a specific physical printing of it. This table is
the *name* level; `printings` is the SKU. See `standards/data-model.md`.

`content_fingerprint` is what makes a re-import cheap and honest: an unchanged card issues no
SQL at all, so "0 added, 0 updated" on a second run is achievable rather than aspirational.
"""
from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base
from .base import TimestampMixin, UuidPrimaryKeyMixin

CARD_TYPES = ("elestral", "spirit", "rune")
ELEMENTS = ("fire", "water", "wind", "earth", "thunder", "frost", "solar", "lunar")
RUNE_TYPES = ("invoke", "counter", "artifact", "stadium", "divine")


class Card(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cards"

    set_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sets.id", ondelete="CASCADE"), nullable=False
    )
    collector_number: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)

    card_type: Mapped[str] = mapped_column(String(16), nullable=False)
    element: Mapped[str | None] = mapped_column(String(16))
    rune_type: Mapped[str | None] = mapped_column(String(16))
    subtype: Mapped[str | None] = mapped_column(String(64))

    attack: Mapped[int | None] = mapped_column(Integer)
    defence: Mapped[int | None] = mapped_column(Integer)
    spirit_cost: Mapped[dict | None] = mapped_column(JSON)

    rules_text: Mapped[str | None] = mapped_column(Text)
    flavour_text: Mapped[str | None] = mapped_column(Text)
    artist: Mapped[str | None] = mapped_column(String(128))

    # SHA-256 over the meaningful fields; excludes id/created_at/updated_at.
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    printings = relationship(
        "Printing", back_populates="card", cascade="all, delete-orphan", lazy="selectin"
    )
    # `selectin`, not `joined`: a page of search results loads its sets in one extra query
    # rather than one per row.
    set = relationship("Set", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("set_id", "collector_number", name="uq_cards_set_number"),
        Index("ix_cards_name", "name"),
        Index("ix_cards_type_element", "card_type", "element"),
    )
