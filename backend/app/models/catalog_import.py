"""`catalog_imports` — one importer run.

Counters are written **once, at terminal status**, not incremented per row. A crash therefore
cannot leave a half-counted run that still claims success.

`cards_unchanged` is an addition to `standards/data-model.md`: "unchanged" is the reported
success signal of a re-run, not the absence of a number. Without it, "0 added, 0 updated"
is indistinguishable from "the importer did nothing at all".
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base
from .base import UuidPrimaryKeyMixin, _utcnow

STATUSES = ("running", "success", "partial", "failed")
TERMINAL_STATUSES = ("success", "partial", "failed")


class CatalogImport(Base, UuidPrimaryKeyMixin):
    __tablename__ = "catalog_imports"

    source: Mapped[str] = mapped_column(String(48), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    # Set iff status is terminal.
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")

    # The sets this run targeted, resolved at start. Recorded so the run-detail response can
    # report coverage for exactly these sets rather than for the whole catalog.
    set_codes: Mapped[list | None] = mapped_column(JSON)

    sets_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cards_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cards_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cards_unchanged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    printings_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_summary: Mapped[str | None] = mapped_column(Text)

    rejections = relationship(
        "ImportRejection", back_populates="catalog_import", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_catalog_imports_status_started", "status", "started_at"),
        Index("ix_catalog_imports_source_started", "source", "started_at"),
    )
