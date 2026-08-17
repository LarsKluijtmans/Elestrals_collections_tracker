"""The service boundary, asserted against a real MySQL — story 002 and story 019.

**These are the tests that make FR-13 true.** Everything else in the suite runs on SQLite, which
has no grants, so a boundary asserted there asserts nothing. Skipped unless
`HARVEST_TEST_MYSQL_URL` and `ELESTRALS_TEST_MYSQL_URL` are both set to the two *narrowly
granted* users — not to root, which would pass every one of these while proving nothing.

    HARVEST_TEST_MYSQL_URL=mysql+pymysql://elestrals_harvest:...@127.0.0.1/elestrals_harvest
    ELESTRALS_TEST_MYSQL_URL=mysql+pymysql://elestrals:...@127.0.0.1/elestrals
    pytest -m mysql

The grants they expect:

    GRANT ALL PRIVILEGES ON elestrals_harvest.*     TO 'elestrals_harvest'@'%';
    GRANT SELECT ON elestrals.sets                  TO 'elestrals_harvest'@'%';
    GRANT SELECT ON elestrals.cards                 TO 'elestrals_harvest'@'%';
    GRANT SELECT ON elestrals.printings             TO 'elestrals_harvest'@'%';
    GRANT SELECT ON elestrals.sealed_products       TO 'elestrals_harvest'@'%';
    GRANT SELECT ON elestrals_harvest.price_daily   TO 'elestrals'@'%';

Table-level rather than schema-level, deliberately: `GRANT SELECT ON elestrals.*` would hand the
harvester every user's inventory the moment somebody adds a table.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

HARVEST_URL = os.environ.get("HARVEST_TEST_MYSQL_URL")
CATALOG_URL = os.environ.get("ELESTRALS_TEST_MYSQL_URL")

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(
        not (HARVEST_URL and CATALOG_URL),
        reason="needs both narrowly-granted MySQL users; see the module docstring",
    ),
]

_REFUSED = (OperationalError, ProgrammingError)


@pytest.fixture(scope="module")
def harvest_engine():
    engine = create_engine(HARVEST_URL, future=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def catalog_engine():
    engine = create_engine(CATALOG_URL, future=True)
    yield engine
    engine.dispose()


class TestTheHarvesterCannotWritePhaseOne:
    """A blocked, broken or rewritten scraper must not be able to touch the collection tracker's
    data. Not by convention — by privilege."""

    @pytest.mark.parametrize("table", ["printings", "cards", "sets", "sealed_products"])
    def test_it_cannot_write_the_catalog(self, harvest_engine, table):
        with harvest_engine.connect() as conn, pytest.raises(_REFUSED):
            conn.execute(text(f"UPDATE elestrals.{table} SET id = id LIMIT 1"))

    @pytest.mark.parametrize("table", ["inventory_items", "user_profiles"])
    def test_it_cannot_even_read_user_data(self, harvest_engine, table):
        """The harvester has no business knowing who owns what, and the grant says so."""
        with harvest_engine.connect() as conn, pytest.raises(_REFUSED):
            conn.execute(text(f"SELECT 1 FROM elestrals.{table} LIMIT 1"))

    @pytest.mark.parametrize("table", ["printings", "cards", "sets", "sealed_products"])
    def test_it_can_read_the_four_catalog_tables(self, harvest_engine, table):
        """The other half: the matcher needs these, so the grant has to exist."""
        with harvest_engine.connect() as conn:
            conn.execute(text(f"SELECT 1 FROM elestrals.{table} LIMIT 1"))


class TestPhaseOneSeesOnlyTheRollup:
    """Story 019: `price_daily` is the entire contract between the services."""

    def test_it_can_read_price_daily(self, catalog_engine):
        with catalog_engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM elestrals_harvest.price_daily LIMIT 1"))

    @pytest.mark.parametrize(
        "table", ["market_listings", "price_observations", "harvest_runs", "price_sources"]
    )
    def test_it_cannot_read_anything_else(self, catalog_engine, table):
        """The temptation this refuses: "just also grant `price_observations` for one query".
        That is a new published contract and a new grant, decided deliberately — not a widening
        of this one."""
        with catalog_engine.connect() as conn, pytest.raises(_REFUSED):
            conn.execute(text(f"SELECT 1 FROM elestrals_harvest.{table} LIMIT 1"))

    def test_it_cannot_write_the_rollup_it_reads(self, catalog_engine):
        with catalog_engine.connect() as conn, pytest.raises(_REFUSED):
            conn.execute(text("UPDATE elestrals_harvest.price_daily SET currency = currency"))
