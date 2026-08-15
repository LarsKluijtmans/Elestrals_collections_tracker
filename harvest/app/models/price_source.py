"""`price_sources` — one row per place we read from, the terms we accepted, and who accepted them.

FR-1 makes this table the gate rather than a config constant. Under **ADR-004** the gate changed
character: it no longer refuses a source whose terms prohibit us, because that decision has been
made and the risk knowingly accepted. What it still refuses is a source where **nobody has
written down what the terms say and put their name to it** — you cannot accept a risk you have
not read.

Two columns carry that, and both are `NOT NULL` before `enabled = 1` by CHECK constraint:

    tos_review_note   what the terms actually say. Prose, because a boolean `reviewed` flag
                      records that someone clicked something, not what they found
    risk_accepted_by  a person. ADR-004 names Lars as the intent-level risk owner; this is the
                      per-source record of the same act

`access_mode` is the honest label for how we obtain the data:

    official_api   a published API used with credentials of our own
    feed           a licensed data feed
    scrape         parsing pages served to a browser — the normal mode under ADR-004

Quarantine (FR-18) lives here too, as a *state of the source* rather than a decision each run
makes: a blocked source stops being asked until its backoff expires.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Integer, Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import TimestampMixin, UuidPrimaryKeyMixin

ACCESS_MODES = ("official_api", "feed", "scrape")


class PriceSource(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "price_sources"

    #: Matches the connector's `name` in `app/harvest/sources/`. The join between a config row
    #: and the code that reads it — a connector with no row cannot run, and vice versa.
    key: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    access_mode: Mapped[str] = mapped_column(String(16), nullable=False)

    #: The kill switch. Flipping it to 0 stops the next scan; no deploy, no restart.
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    tos_review_note: Mapped[str | None] = mapped_column(Text)
    risk_accepted_by: Mapped[str | None] = mapped_column(String(128))
    risk_accepted_on: Mapped[date | None] = mapped_column(Date)
    #: Kept for the record even though ADR-004 does not consult robots.txt. Knowing what it
    #: says is still worth something; treating it as permission is what changed.
    robots_checked_on: Mapped[date | None] = mapped_column(Date)

    rate_limit_per_min: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    #: Influence on the blended median once several sources exist. 1.00 until measured — and
    #: the admin's source-agreement view (story 029) is what measures it.
    weight: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=1.00)

    #: Whether this source reports **completed sales**. Load-bearing, not descriptive: the
    #: runner refuses to write a `sold` observation from a source where this is false, so a
    #: listing that merely vanished can never become a sale.
    reports_sold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- quarantine (FR-18) ---------------------------------------------------------
    quarantined_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quarantine_reason: Mapped[str | None] = mapped_column(String(255))
    #: Consecutive quarantines. Drives the escalating backoff, and reset by a clean run.
    quarantine_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        # FR-1 in the schema. The note can still be lazy prose and the name can still be a
        # nickname — those are social controls — but neither can be *absent*, and no code path
        # can enable a source without both.
        CheckConstraint(
            "enabled = 0 OR (tos_review_note IS NOT NULL AND risk_accepted_by IS NOT NULL)",
            name="ck_price_sources_risk_accepted_before_enabled",
        ),
    )

    def is_quarantined(self, now: datetime) -> bool:
        return self.quarantined_until is not None and self.quarantined_until > now
