"""Notification preferences and the outbox — story 032.

**Outbox-first is the whole design.** A notification is written to `notification_outbox` *before*
any delivery is attempted, and a separate drain sends it. That single ordering is what turns a
notification-api outage into a delay rather than a loss: if delivery is attempted first and the API
is down, the notification only ever existed in a stack frame that has since returned.

Phase 2's price alerts ride on this, which is why story 034 was recorded `blocked` on bolt 009 —
"an outage delays rather than loses" is an acceptance criterion there, not a preference, and there
was no outbox to go through.

Defaults are conservative: **nothing but account-critical mail until the user opts in.** A product
that mails people by default is a product people mute, and a muted channel is worse than no channel
because it looks like it works.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import TimestampMixin, UuidPrimaryKeyMixin

#: `none` is a real choice and the default for everything optional.
CHANNELS = ("none", "email", "inapp", "push")

#: The events this app can raise. `account` is deliberately not configurable — a deletion
#: confirmation is not marketing, and a user who has muted it still needs to receive it.
EVENT_TYPES = ("account", "price_alert", "import_finished", "wishlist_match")

#: Only `account` starts on. Everything else waits to be asked for.
DEFAULT_CHANNELS: dict[str, str] = {
    "account": "email",
    "price_alert": "none",
    "import_finished": "none",
    "wishlist_match": "none",
}

OUTBOX_STATUSES = ("pending", "sent", "dead")

#: Story 032: dead-letter after five. Beyond that the failure is not transient and retrying
#: forever turns one broken address into an unbounded queue.
MAX_ATTEMPTS = 5


class NotificationPreference(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notification_preferences"

    user_sub: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="none")

    __table_args__ = (
        Index("ix_notification_pref_user_event", "user_sub", "event_type", unique=True),
    )


class NotificationOutbox(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notification_outbox"

    user_sub: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)

    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: Exponential backoff. A row is invisible to the drain until this passes, so a failing
    #: recipient does not monopolise every drain cycle.
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # The drain's query: pending, due, oldest first.
        Index("ix_outbox_status_due", "status", "next_attempt_at"),
        Index("ix_outbox_user", "user_sub"),
    )
