"""Importing this package registers every table on `Base.metadata`.

One place, so `alembic/env.py`, `tests/conftest.py` and anything else that needs the metadata
cannot each keep a partial list that drifts.
"""
from __future__ import annotations

from . import (  # noqa: F401
    catalog,
    fx_rate,
    harvest_run,
    market_listing,
    price_daily,
    price_observation,
    price_source,
)

__all__ = [
    "catalog",
    "fx_rate",
    "harvest_run",
    "market_listing",
    "price_daily",
    "price_observation",
    "price_source",
]
