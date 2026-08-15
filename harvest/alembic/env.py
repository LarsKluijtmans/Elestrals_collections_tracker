"""Alembic environment for `elestrals_harvest`.

This tree owns **only** this service's schema. It never migrates `elestrals` — that belongs to
`elestrals-api`, and the database user this connects as has no privilege to try.

`include_object` filters out the read-only catalog mappings. They describe phase 1's tables so
the matcher can read them; autogenerate must never propose creating, altering or dropping one.
"""
from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.models import (  # noqa: F401,E402  (registers the tables)
    catalog,
    fx_rate,
    harvest_run,
    market_listing,
    price_daily,
    price_observation,
    price_source,
)

config = context.config
config.set_main_option("sqlalchemy.url", settings.harvest_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

#: Tables that belong to phase 1 and are mapped here read-only.
_FOREIGN_TABLES = {"sets", "cards", "printings", "sealed_products"}


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    if type_ == "table" and name in _FOREIGN_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=settings.harvest_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        include_object=include_object,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
