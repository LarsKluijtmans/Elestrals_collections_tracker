"""`app_logs` — our own logging table.

Deliberately mirrors the platform's `application_logs` shape so entries are recognisable to
anyone who knows the auth repo, plus `user_sub` and `request_id` so a log line can be joined
against our own domain tables. That joinability is the reason this table exists alongside
logs-api rather than instead of it.

High write volume, so an autoincrement BIGINT primary key rather than a UUID.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import _utcnow

LEVELS = ("debug", "info", "warning", "error", "critical")


class AppLog(Base):
    __tablename__ = "app_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    level: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    component: Mapped[str | None] = mapped_column(String(64))
    operation: Mapped[str | None] = mapped_column(String(64))

    message: Mapped[str] = mapped_column(String(1024), nullable=False)

    user_sub: Mapped[str | None] = mapped_column(String(36))
    request_id: Mapped[str | None] = mapped_column(String(36))
    status_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    # Redacted BEFORE persistence, never on read — a redact-on-read design leaks the
    # moment someone queries the table directly.
    context: Mapped[dict | None] = mapped_column(JSON)
    trace: Mapped[str | None] = mapped_column(Text)

    forwarded_to_platform: Mapped[bool] = mapped_column(default=False, nullable=False)

    __table_args__ = (
        Index("ix_app_logs_at", "at"),
        Index("ix_app_logs_level_at", "level", "at"),
        Index("ix_app_logs_category_at", "category", "at"),
        Index("ix_app_logs_user_at", "user_sub", "at"),
    )
