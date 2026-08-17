"""Shared model mixins, mirroring the platform's `app/models/base.py` convention."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utc_naive(moment: datetime | None = None) -> datetime:
    """UTC, with the tzinfo stripped — for any column that is **compared in SQL**.

    `DateTime(timezone=True)` is a promise neither MySQL nor SQLite keeps: both hand values back
    **naive** whatever the column says. Writing an aware value and comparing against a naive one
    (or the reverse) then produces a query that silently matches nothing, or a `TypeError` in
    Python.

    This project has now been bitten three times. Bolt 014 recorded it first — *"`computed_at`
    comes back naive from both MySQL and SQLite whatever `DateTime(timezone=True)` suggests, so
    the staleness comparison raised"* — and bolt 009's outbox drain hit it again, where the
    failure was worse than an exception: the due-check matched nothing and every notification sat
    pending forever, with no error anywhere.

    So: `created_at`/`updated_at` stay aware (they are only ever read and rendered), and anything a
    `WHERE` clause compares goes through here. Both sides of the comparison, always.
    """
    moment = moment or datetime.now(timezone.utc)
    return moment.astimezone(timezone.utc).replace(tzinfo=None) if moment.tzinfo else moment


class UuidPrimaryKeyMixin:
    """Public IDs are UUIDs. We never expose an auto-increment integer in a response."""

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
