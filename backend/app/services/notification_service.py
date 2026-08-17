"""Notification preferences and the outbox — story 032, and the thing phase 2 has been waiting on.

**Write first, deliver second.** `enqueue` inserts a row and returns; `drain` sends it. That
ordering is the entire mechanism, and reversing it — attempt delivery, write on failure — loses the
notification when the process dies mid-attempt, which is exactly the case an outbox exists for.

Story 034 (price alerts) was recorded `blocked` on this for the same reason: "a notification-api
outage delays rather than loses" is an acceptance criterion there, and there was nothing to delay
*in*.

**Delivery is injected**, so the drain is testable without a network and without mocking a client
library. The default sender raises, which is deliberate: a service wired up without a real sender
should fail loudly on the first drain rather than quietly marking everything sent.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models.base import utc_naive
from ..models.notification import (
    CHANNELS,
    DEFAULT_CHANNELS,
    EVENT_TYPES,
    MAX_ATTEMPTS,
    NotificationOutbox,
    NotificationPreference,
)
from .inventory_service import InventoryError

#: Backoff per attempt, in minutes: 1, 5, 25, 125, 625. Geometric, so a persistent failure backs
#: off quickly rather than retrying a dead address every minute for a week.
BACKOFF_MINUTES = (1, 5, 25, 125, 625)


class UnknownChannel(InventoryError):
    code = "bad_request"
    status = 400


class UnknownEvent(InventoryError):
    code = "bad_request"
    status = 400


class DeliveryFailed(RuntimeError):
    """What a sender raises. Caught by the drain and turned into a retry."""


def _no_sender(entry: NotificationOutbox) -> None:
    raise DeliveryFailed(
        "no notification sender is configured — wire one before draining the outbox"
    )


@dataclass(frozen=True, slots=True)
class DrainResult:
    attempted: int
    sent: int
    retried: int
    dead_lettered: int


class NotificationService:
    def __init__(
        self,
        db: Session,
        sender: Callable[[NotificationOutbox], None] | None = None,
    ) -> None:
        self._db = db
        self._send = sender or _no_sender

    # --- preferences -----------------------------------------------------------------

    def preferences(self, user_sub: str) -> dict[str, str]:
        """Every event type, with the user's choice or the conservative default.

        The full set is returned rather than only what is stored, so a client never has to know
        the defaults — and so adding an event type does not require a migration to backfill rows
        nobody has expressed an opinion about.
        """
        stored = {
            row.event_type: row.channel
            for row in self._db.scalars(
                select(NotificationPreference).where(
                    NotificationPreference.user_sub == user_sub
                )
            )
        }
        return {event: stored.get(event, DEFAULT_CHANNELS[event]) for event in EVENT_TYPES}

    def set_preference(self, user_sub: str, *, event_type: str, channel: str) -> dict[str, str]:
        if event_type not in EVENT_TYPES:
            raise UnknownEvent(f"unknown event type {event_type!r}")
        if channel not in CHANNELS:
            raise UnknownChannel(f"unknown channel {channel!r}")
        if event_type == "account" and channel == "none":
            # Not configurable to `none`. A deletion confirmation is not marketing, and somebody
            # who muted it still needs to receive it.
            raise UnknownChannel(
                "account notifications cannot be turned off — they are things you need to know"
            )

        existing = self._db.scalar(
            select(NotificationPreference).where(
                NotificationPreference.user_sub == user_sub,
                NotificationPreference.event_type == event_type,
            )
        )
        if existing is None:
            self._db.add(NotificationPreference(
                user_sub=user_sub, event_type=event_type, channel=channel,
            ))
        else:
            existing.channel = channel
        self._db.commit()
        return self.preferences(user_sub)

    # --- the outbox ------------------------------------------------------------------

    def enqueue(
        self, user_sub: str, *, event_type: str, subject: str, body: str,
        channel: str | None = None,
    ) -> NotificationOutbox | None:
        """Queue a notification. **Nothing is sent here.**

        Returns `None` when the user has this event set to `none` — respecting the preference at
        *enqueue* time rather than at delivery, so a muted event never occupies the queue at all.
        """
        if event_type not in EVENT_TYPES:
            raise UnknownEvent(f"unknown event type {event_type!r}")

        resolved = channel or self.preferences(user_sub)[event_type]
        if resolved == "none":
            return None

        entry = NotificationOutbox(
            user_sub=user_sub, event_type=event_type, channel=resolved,
            subject=subject[:200], body=body,
            status="pending", attempts=0,
            # NULL, not "now". A fresh entry has no backoff yet, and the drain reads NULL as due
            # — so this is the honest value rather than a timestamp that has to be compared
            # against the drain's clock. It also sidesteps the naive/aware trap entirely for the
            # common case: nothing to compare until something has actually failed.
            next_attempt_at=None,
        )
        self._db.add(entry)
        self._db.commit()
        return entry

    def drain(self, *, limit: int = 50, now: datetime | None = None) -> DrainResult:
        """Attempt delivery for everything pending and due.

        A failure increments the attempt count and pushes `next_attempt_at` out geometrically; the
        fifth failure dead-letters. Story 032: nothing is lost silently, and nothing retries
        forever — a permanently bad address would otherwise be an unbounded queue.
        """
        moment = utc_naive(now)
        due = list(self._db.scalars(
            select(NotificationOutbox)
            .where(
                NotificationOutbox.status == "pending",
                or_(
                    NotificationOutbox.next_attempt_at.is_(None),
                    NotificationOutbox.next_attempt_at <= moment,
                ),
            )
            .order_by(NotificationOutbox.created_at.asc())
            .limit(limit)
        ))

        sent = retried = dead = 0
        for entry in due:
            entry.attempts += 1
            try:
                self._send(entry)
            except Exception as exc:  # noqa: BLE001 — every failure is a retry, whatever it was
                entry.last_error = f"{type(exc).__name__}: {exc}"[:500]
                if entry.attempts >= MAX_ATTEMPTS:
                    entry.status = "dead"
                    dead += 1
                else:
                    minutes = BACKOFF_MINUTES[min(entry.attempts - 1, len(BACKOFF_MINUTES) - 1)]
                    entry.next_attempt_at = moment + timedelta(minutes=minutes)
                    retried += 1
            else:
                entry.status = "sent"
                entry.sent_at = moment
                entry.last_error = None
                sent += 1

        self._db.commit()
        return DrainResult(attempted=len(due), sent=sent, retried=retried, dead_lettered=dead)

    def pending_count(self) -> int:
        return int(self._db.scalar(
            select(func.count(NotificationOutbox.id))
            .where(NotificationOutbox.status == "pending")
        ) or 0)

    def dead_letters(self, *, limit: int = 100) -> list[NotificationOutbox]:
        """Visible to an operator, per story 032's fifth criterion. A dead letter nobody can see
        is a notification that was lost with extra steps."""
        return list(self._db.scalars(
            select(NotificationOutbox)
            .where(NotificationOutbox.status == "dead")
            .order_by(NotificationOutbox.updated_at.desc())
            .limit(limit)
        ))

    def for_user(self, user_sub: str, *, limit: int = 50) -> list[NotificationOutbox]:
        """The in-app inbox: this user's own notifications, newest first."""
        return list(self._db.scalars(
            select(NotificationOutbox)
            .where(NotificationOutbox.user_sub == user_sub)
            .order_by(NotificationOutbox.created_at.desc())
            .limit(limit)
        ))
