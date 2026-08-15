"""Test fixtures.

Unit tests run against in-memory SQLite via `create_all`, exactly as `core/db.py` documents:
Alembic owns the MySQL schema, `create_all` is the unit-test path only. Integration against
real MySQL is a separate, later concern.
"""
from __future__ import annotations

import os

# Before any app import. `price_daily` lives in the harvester's schema on the real deployment and
# is mapped here read-only; on this path everything is one unqualified in-memory database, so the
# qualifier has to be cleared before the model class is defined. Setting it afterwards would be
# too late, and `create_all` would fail looking for a schema SQLite does not have.
os.environ["HARVEST_SCHEMA"] = ""

from contextlib import contextmanager  # noqa: E402

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base

# Importing the modules registers the tables on Base.metadata.
from app.models import (  # noqa: F401
    app_log,
    card,
    catalog_import,
    import_rejection,
    inventory_item,
    price_daily,
    printing,
    sealed_product,
    user_profile,
)
from app.models import (  # noqa: F401
    set as set_model,
)
from app.models import set_completion  # noqa: F401

_WRITE_PREFIXES = ("INSERT", "UPDATE", "DELETE")


@pytest.fixture()
def engine():
    # StaticPool + check_same_thread=False: `TestClient` runs the app on another thread, and
    # a default in-memory SQLite connection is bound to the thread that created it. One
    # shared connection is also what keeps `:memory:` a single database across sessions.
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        Base.metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture(autouse=True)
def _log_to_the_test_database(engine, monkeypatch):
    """`log_event` deliberately opens its own session so a log write survives a rolled-back
    request. Left alone under test that means a real MySQL connection attempt per logged
    event — silently swallowed, but ~2s of dead time on every API request. Point it at the
    test database instead: the events still get written and can be asserted on.
    """
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    monkeypatch.setattr("app.services.logging_service.SessionLocal", factory)


@pytest.fixture()
def db(engine) -> Session:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def count_writes(engine):
    """Count INSERT/UPDATE/DELETE statements actually issued.

    The idempotency criterion is asserted against *this*, not against the importer's own
    counters — those could report 0 added / 0 updated while still rewriting every row, which
    is precisely the failure mode a naive `ON DUPLICATE KEY UPDATE` produces.
    """
    seen: list[str] = []

    def before(conn, cursor, statement, parameters, context, executemany):
        head = statement.lstrip().upper()
        if head.startswith(_WRITE_PREFIXES):
            seen.append(statement)

    event.listen(engine, "before_cursor_execute", before)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", before)
