"""`price_alerts` — story 034.

Lives in `elestrals` rather than the harvester's schema, and that placement is FR-13 rather than
convenience: an alert is a *user's* row, and `harvest-api` holds no grant on user data. The
harvester publishes `price_daily`; this service reads it, decides, and delivers through the phase-1
outbox.

Three fields carry the story's rules:

* `direction` — an alert is "tell me when it goes above X" or "below X", never a bare threshold.
  Which side matters is the whole question, and a threshold without it fires on both.
* `cooldown_until` — a price that oscillates around a threshold must not fire every evaluation.
  One notification about a crossing is information; six is a reason to mute the channel.
* `is_active` — deactivating stops it firing immediately, without losing the threshold somebody
  chose. Deletion is also available; they are different intentions.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base
from .base import TimestampMixin, UuidPrimaryKeyMixin

DIRECTIONS = ("above", "below")

#: Story 034: a fired alert does not fire again within this window. Long enough that a price
#: wobbling over a threshold produces one notification rather than a stream.
COOLDOWN_DAYS = 7


class PriceAlert(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "price_alerts"

    user_sub: Mapped[str] = mapped_column(String(36), nullable=False)
    printing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("printings.id", ondelete="CASCADE"), nullable=False
    )

    direction: Mapped[str] = mapped_column(String(8), nullable=False, default="below")
    threshold_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    #: Money always travels with its currency — standards §3, and the same rule
    #: `wishlist_items.max_price_cents` follows.
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Compared in a WHERE clause, so naive UTC — see `models/base.utc_naive`.
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    printing = relationship("Printing", lazy="selectin")

    __table_args__ = (
        # One alert per direction per printing per user. Two "below €20" alerts on one card is a
        # double notification, not a feature.
        UniqueConstraint(
            "user_sub", "printing_id", "direction", name="uq_price_alert_user_printing_direction"
        ),
        CheckConstraint("threshold_cents > 0", name="ck_price_alert_threshold_positive"),
        Index("ix_price_alerts_active", "is_active", "printing_id"),
        Index("ix_price_alerts_user", "user_sub"),
    )
