"""Engine and session factory for `elestrals_harvest`.

This service connects as a user that holds **no write grant** on `elestrals`. That is the
boundary FR-13 is built on, and it is enforced by MySQL rather than by this file — the point of
a grant is that it holds even when the code is wrong.

`Base.metadata.create_all` is the unit-test path against in-memory SQLite only. Alembic owns the
MySQL schema, in this service's own tree, and neither service migrates the other's.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..config import settings


class Base(DeclarativeBase):
    pass


def catalog_schema() -> str | None:
    """The schema phase-1 catalog tables live in, or `None` on the SQLite test path.

    Read through a function rather than baked into the models at import time: the test suite
    points it at `None` so the read-only catalog mappings resolve to unqualified tables in the
    same in-memory database.
    """
    return settings.catalog_schema or None


engine = create_engine(
    settings.harvest_database_url,
    echo=settings.db_echo,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
