"""Read access to the harvester's `price_daily`. The only cross-schema query this service makes.

Every method here is a `SELECT`. There is no write path, and no grant for one — see
`models/price_daily.py`.

Two shapes, and both are deliberate:

* **`latest_for_printings`** takes a *set* of printings and returns their most recent rollup in
  one query. Valuation over 5,000 holdings must not become 5,000 lookups; the NFR is 1.5s p95.
* **`history_for_printing`** takes one printing and a range. That is the price tab, and it reads
  rollups only — never the fact table, which lives behind a grant this service does not hold.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.base import utc_today
from ..models.price_daily import PriceDaily


class PriceRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def history_for_printing(
        self,
        printing_id: str,
        *,
        since: date | None = None,
        sale_type: str = "sold",
        condition: str | None = None,
    ) -> list[PriceDaily]:
        stmt = select(PriceDaily).where(
            PriceDaily.printing_id == printing_id,
            PriceDaily.sale_type == sale_type,
        )
        if since:
            stmt = stmt.where(PriceDaily.day >= since)
        if condition is not None:
            stmt = stmt.where(PriceDaily.condition_key == condition)
        return list(self._db.scalars(stmt.order_by(PriceDaily.day)))

    def latest_for_printings(
        self,
        printing_ids: list[str],
        *,
        sale_type: str = "sold",
        currency: str | None = None,
    ) -> dict[tuple[str, str], PriceDaily]:
        """`(printing_id, condition_key) -> most recent rollup`, in one query.

        Valuation's read. A per-holding lookup would be correct and would also be 5,000 round
        trips, which is the difference between the NFR budget and a page nobody waits for.
        """
        if not printing_ids:
            return {}

        newest = (
            select(
                PriceDaily.printing_id.label("printing_id"),
                PriceDaily.condition_key.label("condition_key"),
                func.max(PriceDaily.day).label("day"),
            )
            .where(
                PriceDaily.printing_id.in_(printing_ids),
                PriceDaily.sale_type == sale_type,
            )
            .group_by(PriceDaily.printing_id, PriceDaily.condition_key)
            .subquery()
        )
        stmt = select(PriceDaily).join(
            newest,
            (PriceDaily.printing_id == newest.c.printing_id)
            & (PriceDaily.condition_key == newest.c.condition_key)
            & (PriceDaily.day == newest.c.day),
        ).where(PriceDaily.sale_type == sale_type)
        if currency:
            stmt = stmt.where(PriceDaily.currency == currency)

        return {
            (row.printing_id, row.condition_key): row
            for row in self._db.scalars(stmt)
            if row.printing_id
        }

    def on_or_before(
        self,
        printing_ids: list[str],
        day,
        *,
        sale_type: str = "sold",
        currency: str | None = None,
    ) -> dict[tuple[str, str], PriceDaily]:
        """`(printing_id, condition_key) -> the newest rollup **on or before `day`**`.

        Story 022's back-fill reads this, and the "on or before" is the whole point: a snapshot
        for 3 March must be valued with 3 March's prices, not today's. Valuing history with
        today's rollups would make the entire chart move every night — the same failure as using
        today's FX rate for a year-old sale, which story 018 refuses for the same reason.

        "On or before" rather than "on", because rollups exist only for days with observations.
        Carrying the last known price forward is what a price *is* between sales; the alternative
        is a chart that is mostly holes.
        """
        if not printing_ids:
            return {}

        newest = (
            select(
                PriceDaily.printing_id.label("printing_id"),
                PriceDaily.condition_key.label("condition_key"),
                func.max(PriceDaily.day).label("day"),
            )
            .where(
                PriceDaily.printing_id.in_(printing_ids),
                PriceDaily.sale_type == sale_type,
                PriceDaily.day <= day,
            )
            .group_by(PriceDaily.printing_id, PriceDaily.condition_key)
            .subquery()
        )
        stmt = select(PriceDaily).join(
            newest,
            (PriceDaily.printing_id == newest.c.printing_id)
            & (PriceDaily.condition_key == newest.c.condition_key)
            & (PriceDaily.day == newest.c.day),
        ).where(PriceDaily.sale_type == sale_type)
        if currency:
            stmt = stmt.where(PriceDaily.currency == currency)

        return {
            (row.printing_id, row.condition_key): row
            for row in self._db.scalars(stmt)
            if row.printing_id
        }

    def earliest_day(self):
        """The first day any rollup exists for.

        Story 022: before this, values are null and the chart honestly starts later than the
        counts do. The counts are still real history and worth showing — a chart that began at
        the first *price* would throw away months of true collection growth.
        """
        return self._db.scalar(select(func.min(PriceDaily.day)))

    def movers(
        self,
        *,
        window_days: int = 7,
        min_observations: int = 3,
        limit: int = 10,
        currency: str = "EUR",
    ) -> list[tuple[str, int, int, float]]:
        """`(printing_id, then_cents, now_cents, pct)` — biggest movers, up and down.

        `min_observations` is the difference between a market overview and a noise generator:
        without it the list is dominated by printings with one sale each, which is exactly the
        data least worth ranking.
        """
        today = utc_today()
        then = today - timedelta(days=window_days)

        recent = self._window(then, today, min_observations, currency)
        earlier = self._window(then - timedelta(days=window_days), then, min_observations, currency)

        out: list[tuple[str, int, int, float]] = []
        for printing_id, now_cents in recent.items():
            was = earlier.get(printing_id)
            if not was:
                continue
            out.append((printing_id, was, now_cents, ((now_cents - was) / was) * 100))
        out.sort(key=lambda row: abs(row[3]), reverse=True)
        return out[:limit]

    def _window(
        self, start: date, end: date, min_observations: int, currency: str
    ) -> dict[str, int]:
        rows = self._db.execute(
            select(
                PriceDaily.printing_id,
                func.avg(PriceDaily.median_cents),
                func.sum(PriceDaily.observation_count),
            )
            .where(
                PriceDaily.sale_type == "sold",
                PriceDaily.currency == currency,
                PriceDaily.day >= start,
                PriceDaily.day < end,
                PriceDaily.printing_id.is_not(None),
            )
            .group_by(PriceDaily.printing_id)
            .having(func.sum(PriceDaily.observation_count) >= min_observations)
        ).all()
        return {row[0]: int(row[1]) for row in rows if row[0] and row[1]}

    def last_computed_at(self):
        """When the harvester last published. Shown next to figures so a stale rollup says so
        rather than looking current — FR-13's "degrades freshness, never availability"."""
        return self._db.scalar(select(func.max(PriceDaily.computed_at)))
