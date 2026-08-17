"""`saved_views` — a named filter set, sort and density — story 021.

The stored `filters` blob is deliberately **the same shape the URL serialises**. Story 020 makes a
filtered collection a shareable artifact by putting the filter state in the query string; a saved
view is that same state with a name on it. Two encodings of one concept would drift, and the drift
would surface as a saved view that restores something subtly different from the link you shared.

So the flow is one-way and lossless: URL → `FilterSet` → JSON → `FilterSet` → URL.

Views are per-user and there is no sharing mechanism. `user_sub` leads the unique key and the index,
as everywhere else a user owns rows.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import TimestampMixin, UuidPrimaryKeyMixin

DENSITIES = ("comfortable", "compact")


class SavedView(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "saved_views"

    user_sub: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    #: The serialised `FilterSet`. `JSON` rather than `Text`: MySQL 8 and SQLite both have a real
    #: JSON type, and storing a string means every read is a parse the database could have done.
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    sort: Mapped[str] = mapped_column(String(32), nullable=False, default="added_desc")
    density: Mapped[str] = mapped_column(String(16), nullable=False, default="comfortable")

    __table_args__ = (
        # Names are the handle a collector uses, so two views called "Fire holos" would be a
        # usability bug rather than a data one — refused at the schema so no service can forget.
        UniqueConstraint("user_sub", "name", name="uq_saved_view_user_name"),
        Index("ix_saved_view_user", "user_sub"),
    )
