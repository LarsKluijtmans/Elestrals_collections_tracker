"""The nightly collection snapshot — the phase-1 job that phase 2 reads.

Nothing in phase 1 uses what this writes. That is not an argument against it; it is the entire
design. Portfolio history cannot be reconstructed after the fact — the counts for 3 March exist only
if somebody wrote them on 3 March — so this runs from launch and the chart is already populated on
the day the portfolio page ships.

The inception log called it "cheap insurance taken a year early". It then went unbuilt for long
enough that three phase-2 stories were recorded `blocked` on it, which is the one outcome planning
it early existed to prevent.

**Idempotent by construction.** `uq_collection_snapshot_user_day` means running twice for one day
updates rather than appends, so the job is safe to re-run after a failure, safe to run manually, and
safe for phase 2 to come back to and fill in `total_value_cents` on the same row.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.collection_snapshot import CollectionSnapshot
from ..models.inventory_item import InventoryItem


@dataclass(frozen=True, slots=True)
class SnapshotResult:
    taken_on: date
    users: int
    written: int
    updated: int


class SnapshotService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def take(self, *, taken_on: date | None = None) -> SnapshotResult:
        """One row per user who holds anything, for the given day (default: today).

        Users with an empty collection are **skipped rather than written as zero**. A row saying
        "0 cards on 3 March" for somebody who signed up in June is not history, it is invention —
        and phase 2 would draw it as a flat line at the bottom of their chart.
        """
        day = taken_on or datetime.now(timezone.utc).date()

        totals = self._db.execute(
            select(
                InventoryItem.user_sub,
                func.coalesce(func.sum(InventoryItem.quantity), 0),
                func.count(func.distinct(InventoryItem.printing_id)),
            ).group_by(InventoryItem.user_sub)
        ).all()

        written = updated = 0
        for user_sub, item_count, distinct_printings in totals:
            existing = self._db.scalar(
                select(CollectionSnapshot).where(
                    CollectionSnapshot.user_sub == user_sub,
                    CollectionSnapshot.taken_on == day,
                )
            )
            if existing is None:
                self._db.add(CollectionSnapshot(
                    user_sub=user_sub,
                    taken_on=day,
                    item_count=int(item_count),
                    distinct_printings=int(distinct_printings),
                    # Phase 1 counts; it does not value. NULL and `none` say so honestly, and
                    # phase 2's nightly valuation fills both in on this same row.
                    total_value_cents=None,
                    valuation_confidence="none",
                ))
                written += 1
            else:
                existing.item_count = int(item_count)
                existing.distinct_printings = int(distinct_printings)
                # `total_value_cents` is deliberately not touched. If phase 2 has already valued
                # this day, re-running the phase-1 counter must not erase that.
                updated += 1

        self._db.commit()
        return SnapshotResult(
            taken_on=day, users=len(totals), written=written, updated=updated
        )

    def value_days(
        self,
        portfolio,
        items,
        *,
        since: date | None = None,
        currency: str = "EUR",
    ) -> tuple[int, int]:
        """Story 022's back-fill: write a value onto every snapshot, using **its own day's** prices.

        Returns `(valued, left_null)`.

        Two properties this has to have, and they are the story's own criteria:

        * **Re-runnable, producing the same values for the same days.** It reads `price_daily`,
          which is itself recomputed rather than accumulated, so running this twice is running the
          same arithmetic over the same inputs.
        * **Never today's prices for a past day.** Valuing history with current rollups would make
          the whole chart move every night — the same failure as using today's FX rate for a
          year-old sale.

        A user's *current* holdings are the best available proxy for what they held on a past day,
        and that is a real limitation rather than a bug: phase 1 recorded counts, not composition.
        So back-filled values are honest about their prices and approximate about their contents,
        and days from here on are exact because the snapshot and the valuation happen together.
        """
        rows = self._db.scalars(
            select(CollectionSnapshot).where(
                CollectionSnapshot.taken_on >= since
            ) if since else select(CollectionSnapshot)
        )

        valued = left_null = 0
        holdings_by_user: dict[str, list] = {}
        for row in rows:
            if row.user_sub not in holdings_by_user:
                holdings_by_user[row.user_sub] = items.all_for_user(row.user_sub)
            portfolio.value_snapshot(
                row, holdings_by_user[row.user_sub], currency=currency,
            )
            if row.total_value_cents is None:
                left_null += 1
            else:
                valued += 1

        self._db.commit()
        return valued, left_null

    def history(
        self, user_sub: str, *, since: date | None = None, limit: int = 400
    ) -> list[CollectionSnapshot]:
        """A user's own series, oldest first — the shape a chart wants.

        Owner-scoped like every other read of user data, and ordered ascending because a caller
        that has to reverse a series before plotting it will eventually forget to.
        """
        stmt = select(CollectionSnapshot).where(CollectionSnapshot.user_sub == user_sub)
        if since is not None:
            stmt = stmt.where(CollectionSnapshot.taken_on >= since)
        return list(
            self._db.scalars(stmt.order_by(CollectionSnapshot.taken_on.asc()).limit(limit))
        )
