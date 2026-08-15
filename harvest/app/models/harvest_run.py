"""`harvest_runs` — one row per scan, inserted **before** the work starts.

Named `harvest_runs`, not `scrape_runs` as `standards/data-model.md` has it. The rename is
deliberate and is the same kind of delta `catalog_imports.cards_unchanged` was: ADR-003 closed
the scraping route, so every row this table will ever hold describes an API read or a licensed
feed. Calling the table `scrape_runs` would leave the codebase describing an activity it does
not perform, and the operator console reads the column names.

Two modes, and the difference is which questions get asked, not which source answers:

    deep    the whole query space — every set, every tracked card name, every sealed term.
            Finds items we have never seen. Expensive; runs on a slow schedule.
    light   only what we already know: re-check known live listings, then one narrow
            "more like this" query per product. Cheap; runs often.

Counters are written **once, at terminal status**, exactly as `catalog_imports` does, so a
crash cannot leave a half-counted run that still claims success. A run left `running` past
`harvest_run_stale_after_minutes` is swept to `failed` by
`HarvestRunRepository.sweep_stale()` — FR-2 requires that a crashed run does not sit
`running` forever, holding a lock nobody is holding.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import UuidPrimaryKeyMixin, _utcnow

MODES = ("deep", "light")
STATUSES = ("running", "success", "partial", "failed")
TERMINAL_STATUSES = ("success", "partial", "failed")


class HarvestRun(Base, UuidPrimaryKeyMixin):
    __tablename__ = "harvest_runs"

    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("price_sources.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(8), nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")

    #: How many questions the plan asked. A deep run whose query count collapses has lost the
    #: catalog, not the market.
    queries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Matched above the confidence floor and written. `parsed - accepted` is the reject rate
    #: story 012's operations console trends — a sustained drop means the matcher broke or the
    #: source changed its titles, and both look identical from the outside.
    accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: Listings seen for the first time ever. The deep scan's whole purpose.
    discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Known listings that were live last run and are gone now. The light scan's whole
    #: purpose. NOT a sale count — see `market_listing.py`.
    ended: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_summary: Mapped[str | None] = mapped_column(Text)

    #: `schedule` or `admin`. An operator reading a run needs to know whether a human asked for
    #: it, and the answer is not recoverable from the timestamps once beat and a person have
    #: both been at it.
    triggered_by: Mapped[str] = mapped_column(String(16), nullable=False, default="schedule")
    #: Story 027's stop button. The scan checks it between queries so it stops at a clean
    #: boundary and finishes its own run row — killing the worker would leave a `running` row
    #: for the sweeper, which works but records the wrong cause.
    stop_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_harvest_runs_source_started", "source_id", "started_at"),
        Index("ix_harvest_runs_status_started", "status", "started_at"),
    )
