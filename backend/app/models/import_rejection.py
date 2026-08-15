"""`import_rejections` — a source record that could not be mapped, kept whole with a reason.

This table exists so a rejection is *reportable*, not merely logged. `raw_record` carries what
actually arrived so an operator can see the input, not just that something failed — passed
through `redact()` first, because a source file can contain anything.

Append-only: rows are never updated after the run finishes.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base
from .base import UuidPrimaryKeyMixin, _utcnow

REASON_CODES = (
    "unknown_rarity",
    "unknown_finish",
    "unknown_edition",
    "conflicting_card_fields",
    "missing_required_field",
    "invalid_spirit_cost",
    "type_field_mismatch",
    "duplicate_printing_key",
    "unknown_set",
)


class ImportRejection(Base, UuidPrimaryKeyMixin):
    __tablename__ = "import_rejections"

    import_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_imports.id", ondelete="CASCADE"), nullable=False
    )

    # Where it came from, precisely enough to fix by hand: "FE01.csv:42".
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_record: Mapped[dict | None] = mapped_column(JSON)

    reason_code: Mapped[str] = mapped_column(String(48), nullable=False)
    field: Mapped[str | None] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    catalog_import = relationship("CatalogImport", back_populates="rejections")

    __table_args__ = (Index("ix_import_rejections_import_reason", "import_id", "reason_code"),)
