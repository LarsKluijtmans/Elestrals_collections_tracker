"""Read-only mappings onto phase 1's `elestrals` schema.

The matcher has to resolve a title against real printings, so this service reads four catalog
tables cross-schema. It holds a `SELECT` grant on exactly these four and nothing else — no
`inventory_items`, no `user_profiles`. The harvester has no business knowing who owns what.

Nothing here is ever written. There is no grant to write it, so a mistake surfaces as a
permission error rather than as a corrupted catalog, which is the whole point of splitting the
services at the database rather than at a code boundary.

The schema qualifier comes from `core.db.catalog_schema()` so the unit-test path can resolve
these to unqualified tables in one SQLite database.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base, catalog_schema


class CatalogSet(Base):
    __tablename__ = "sets"
    __table_args__ = {"schema": catalog_schema()}

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(128))
    card_count: Mapped[int] = mapped_column(Integer)


class CatalogCard(Base):
    __tablename__ = "cards"
    __table_args__ = {"schema": catalog_schema()}

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    set_id: Mapped[str] = mapped_column(String(36))
    collector_number: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(160))


class CatalogPrinting(Base):
    __tablename__ = "printings"
    __table_args__ = {"schema": catalog_schema()}

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    card_id: Mapped[str] = mapped_column(String(36))
    rarity: Mapped[str] = mapped_column(String(16))
    finish: Mapped[str] = mapped_column(String(16))
    language: Mapped[str] = mapped_column(String(5))
    edition: Mapped[str] = mapped_column(String(16))
    #: Phase 1 sets this so phase 2 can stop spending requests on dead SKUs. The query planner
    #: honouring it is what makes it more than a comment.
    is_tracked_for_price: Mapped[bool] = mapped_column(Boolean)


class CatalogSealedProduct(Base):
    __tablename__ = "sealed_products"
    __table_args__ = {"schema": catalog_schema()}

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    set_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(24))
    name: Mapped[str] = mapped_column(String(160))
    is_tracked_for_price: Mapped[bool] = mapped_column(Boolean)
