"""`sets` — a released product line.

`card_count` is the **printed** set size and is declared in the seed, never derived from how
many rows an import managed to write. Deriving it would make an incomplete catalog report
100% completion — a wrong answer that looks right, which is worse than an obvious failure.
See `ddd-01-domain-model.md`.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import TimestampMixin, UuidPrimaryKeyMixin


class Set(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sets"

    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    series: Mapped[str | None] = mapped_column(String(64))
    released_on: Mapped[date | None] = mapped_column(Date())

    # The completion denominator. Declared, not counted.
    card_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    logo_asset_url: Mapped[str | None] = mapped_column(String(512))

    __table_args__ = (Index("ix_sets_series", "series"),)
