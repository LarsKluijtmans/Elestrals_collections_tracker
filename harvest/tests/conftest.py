"""Test fixtures for `harvest-api`.

Unit tests run against in-memory SQLite, exactly as `core/db.py` documents: Alembic owns the
MySQL schema, `create_all` is the unit-test path only.

**`CATALOG_SCHEMA` is cleared before any app import**, and that ordering is load-bearing. The
read-only catalog mappings resolve their schema qualifier at class-definition time, so on the
real deployment they read `elestrals.printings` and here they read an unqualified `printings` in
the same in-memory database. Setting it after the import would be too late and every catalog
query would fail looking for a schema SQLite does not have.

The grant boundary that separates the two services cannot be tested here at all — SQLite has no
grants, so a boundary asserted on this path would assert nothing. `test_grants_mysql.py` carries
those tests and is marked `mysql`.
"""
from __future__ import annotations

import os

# Before any app import. See the module docstring.
os.environ["CATALOG_SCHEMA"] = ""
os.environ.setdefault("HARVEST_CONTACT_EMAIL", "ops@example.com")
os.environ.setdefault("ENVIRONMENT", "local")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.db import Base  # noqa: E402
from app.models import (  # noqa: F401,E402  (registers the tables)
    catalog, fx_rate, harvest_run, market_listing, price_daily, price_observation, price_source,
)
from app.models.catalog import (  # noqa: E402
    CatalogCard, CatalogPrinting, CatalogSealedProduct, CatalogSet,
)
from app.models.price_source import PriceSource  # noqa: E402


@pytest.fixture()
def engine():
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


@pytest.fixture()
def db(engine) -> Session:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _quiet_logs(monkeypatch):
    """`log_event` writes to stdout by design. Silenced here so a failing assertion is readable
    rather than buried in a run's worth of structured JSON."""
    for module in (
        "app.services.logging_service",
        "app.services.harvest_runner",
        "app.main",
        "app.controllers.admin_sources",
        "app.controllers.admin_runs",
    ):
        monkeypatch.setattr(f"{module}.log_event", lambda *a, **k: None)


@pytest.fixture()
def catalog_rows(db):
    """A small catalog: one set, one card with two printings, one sealed product.

    Written directly rather than through phase 1's importer — this service has no write grant on
    the catalog in production, and the tests should not pretend otherwise beyond what SQLite
    forces.
    """
    base = CatalogSet(id="set-1", code="FE01", name="Base Set", card_count=126)
    card = CatalogCard(id="card-1", set_id="set-1", collector_number="012", name="Vipyro")
    printings = [
        CatalogPrinting(id="p-normal", card_id="card-1", rarity="rare", finish="normal",
                        language="en", edition="first", is_tracked_for_price=True),
        CatalogPrinting(id="p-foil", card_id="card-1", rarity="holo_rare", finish="foil",
                        language="en", edition="first", is_tracked_for_price=True),
    ]
    sealed = CatalogSealedProduct(
        id="s-box", set_id="set-1", kind="booster_box", name="Base Set Booster Box",
        is_tracked_for_price=True,
    )
    db.add_all([base, card, *printings, sealed])
    db.commit()
    return {"set": base, "card": card, "printings": printings, "sealed": sealed}


@pytest.fixture()
def source(db) -> PriceSource:
    """An enabled source with its risk accepted — the state the gate demands."""
    row = PriceSource(
        key="fake", name="Fake source", base_url="https://fake.test",
        access_mode="scrape", enabled=True,
        tos_review_note="Read 2026-08-15: the terms prohibit this. Accepted per ADR-004.",
        risk_accepted_by="Test Suite",
        rate_limit_per_min=60, weight=1.0, reports_sold=False,
    )
    db.add(row)
    db.commit()
    return row
