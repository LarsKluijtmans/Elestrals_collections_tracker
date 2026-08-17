"""Shared model mixins, mirroring `elestrals-api`'s `app/models/base.py`.

A copy rather than a shared package, deliberately: the two services share *conventions*, not
code. A common library between them is a coupling that gets regretted the first time one needs
a convention the other does not want — and this is nine lines.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utc_today() -> date:
    """Today **in UTC**, for any `date` column or window.

    The mirror of `elestrals-api`'s `utc_today`, and a copy for the same reason the rest of this
    file is a copy. Every day-stamped row on this side is UTC — `price_daily.day`, the FX day,
    `risk_accepted_on` — while the reads were `date.today()`, which is the *local* day.

    They agree for twenty-two hours and disagree for the other two. Running in UTC+2, between local
    midnight and UTC midnight `date.today()` is a day ahead of everything already written, so the
    FX task asks for a rate that has not been published yet and the maintenance window starts a day
    late. Found on 2026-08-18 by a snapshot test on the other service that failed at 00:47 and
    would have passed again by 02:00.
    """
    return datetime.now(timezone.utc).date()


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
