"""Shared model mixins, mirroring `elestrals-api`'s `app/models/base.py`.

A copy rather than a shared package, deliberately: the two services share *conventions*, not
code. A common library between them is a coupling that gets regretted the first time one needs
a convention the other does not want — and this is nine lines.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
