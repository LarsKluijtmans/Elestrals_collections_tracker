"""All database access for `harvest_runs`, `market_listings`, `price_observations` and
`price_daily`.

One repository, because a scan writes the first three inside one unit of work and splitting them
would only mean three objects that must be committed in the right order.

Three rules worth reading before changing anything:

* **`record_observation` is insert-or-ignore, not upsert.** `UNIQUE (source_id, external_id)` is
  what makes re-running a scan free (FR-3), and the right response to hitting it is to do nothing.
  Updating instead would let a second look rewrite the price recorded the first time, which is how
  a fact table quietly becomes a cache.
* **`last_seen_at` moves only in `mark_seen`.** A scan that did not ask about a listing must not
  refresh it, or "gone" becomes indistinguishable from "not asked about lately" — and the light
  scan is built entirely on that distinction.
* **Catalog names are not joined here.** This service can read four `elestrals` tables, but the
  explorer's queries stay inside `elestrals_harvest` and resolve names in a second pass through
  `CatalogSnapshotRepository`. A cross-schema join in every list query would make the boundary
  load-bearing for performance, which is the fastest way to end up widening it.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..models.harvest_run import HarvestRun
from ..models.market_listing import MarketListing
from ..models.price_daily import PriceDaily
from ..models.price_observation import PriceObservation


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HarvestRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    @property
    def session(self) -> Session:
        return self._db

    # --- runs -----------------------------------------------------------------------

    def start_run(self, source_id: str, mode: str, *, triggered_by: str = "schedule") -> HarvestRun:
        """Inserted **before** any work starts (FR-2), so a crash leaves evidence."""
        run = HarvestRun(
            source_id=source_id, mode=mode, status="running", triggered_by=triggered_by
        )
        self._db.add(run)
        self._db.commit()
        return run

    def get_run(self, run_id: str) -> HarvestRun | None:
        return self._db.get(HarvestRun, run_id)

    def running_run(self, source_id: str, mode: str) -> HarvestRun | None:
        """The one that makes a duplicate trigger a `409` rather than a silent second queue."""
        return self._db.scalar(
            select(HarvestRun).where(
                HarvestRun.source_id == source_id,
                HarvestRun.mode == mode,
                HarvestRun.status == "running",
            )
        )

    def finish_run(
        self,
        run: HarvestRun,
        *,
        status: str,
        counts: dict[str, int],
        error_summary: str | None = None,
    ) -> HarvestRun:
        run.status = status
        run.finished_at = _utcnow()
        for key, value in counts.items():
            setattr(run, key, value)
        run.error_summary = error_summary
        self._db.commit()
        return run

    def request_stop(self, run: HarvestRun) -> HarvestRun:
        run.stop_requested = True
        self._db.commit()
        return run

    def stop_requested(self, run_id: str) -> bool:
        """Read fresh from the database, not from a cached object: the flag is set by a web
        request in another process, and an ORM instance the worker loaded an hour ago will
        never see it."""
        self._db.expire_all()
        value = self._db.scalar(
            select(HarvestRun.stop_requested).where(HarvestRun.id == run_id)
        )
        return bool(value)

    def sweep_stale(self, *, older_than_minutes: int) -> int:
        """Fail runs that have been `running` too long to still be running.

        FR-2's last criterion. A process killed mid-scan leaves a `running` row that makes the
        console report a scan in progress forever, and makes "did last night's run finish?"
        unanswerable.
        """
        cutoff = _utcnow() - timedelta(minutes=older_than_minutes)
        stale = list(self._db.scalars(
            select(HarvestRun).where(
                HarvestRun.status == "running", HarvestRun.started_at < cutoff
            )
        ))
        for run in stale:
            run.status = "failed"
            run.finished_at = _utcnow()
            run.error_summary = (
                f"swept: still 'running' more than {older_than_minutes} minutes after it "
                "started, so the process that owned it is gone"
            )
        if stale:
            self._db.commit()
        return len(stale)

    def latest_run(self, source_id: str, *, mode: str | None = None) -> HarvestRun | None:
        stmt = (
            select(HarvestRun)
            .where(HarvestRun.source_id == source_id)
            .order_by(HarvestRun.started_at.desc())
            .limit(1)
        )
        if mode:
            stmt = stmt.where(HarvestRun.mode == mode)
        return self._db.scalar(stmt)

    def list_runs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        source_id: str | None = None,
        mode: str | None = None,
        status: str | None = None,
    ) -> list[HarvestRun]:
        stmt = select(HarvestRun).order_by(HarvestRun.started_at.desc())
        if source_id:
            stmt = stmt.where(HarvestRun.source_id == source_id)
        if mode:
            stmt = stmt.where(HarvestRun.mode == mode)
        if status:
            stmt = stmt.where(HarvestRun.status == status)
        return list(self._db.scalars(stmt.limit(limit).offset(offset)))

    def accept_rate_trend(
        self, source_id: str, *, mode: str, limit: int = 30
    ) -> list[tuple[datetime, int, int]]:
        """`(started_at, parsed, accepted)` for the last N runs, oldest first.

        Per mode, deliberately. A deep scan's accept rate is legitimately lower than a light
        scan's — it asks broader questions and gets more unrelated results — and merging them
        hides both signals.
        """
        rows = self._db.execute(
            select(HarvestRun.started_at, HarvestRun.parsed, HarvestRun.accepted)
            .where(
                HarvestRun.source_id == source_id,
                HarvestRun.mode == mode,
                HarvestRun.status.in_(("success", "partial")),
            )
            .order_by(HarvestRun.started_at.desc())
            .limit(limit)
        ).all()
        return [(r[0], int(r[1] or 0), int(r[2] or 0)) for r in reversed(rows)]

    # --- listings -------------------------------------------------------------------

    def find_listing(self, source_id: str, external_id: str) -> MarketListing | None:
        return self._db.scalar(
            select(MarketListing).where(
                MarketListing.source_id == source_id,
                MarketListing.external_id == external_id,
            )
        )

    def get_listing(self, listing_id: str) -> MarketListing | None:
        return self._db.get(MarketListing, listing_id)

    def save_listing(self, values: dict) -> tuple[MarketListing, bool]:
        """Insert or update one listing. Returns `(row, was_created)`.

        Read-then-write rather than a single upsert, because the caller needs to know whether the
        listing is new — `discovered` is the deep scan's headline number and cannot be recovered
        from an upsert's row count. Safe because one source runs one scan at a time (the kill
        switch, the rate limit and the duplicate-run refusal are all per source), and
        `uq_market_listings_source_external` is the backstop if that ever stops being true.
        """
        existing = self.find_listing(values["source_id"], values["external_id"])
        if existing is None:
            row = MarketListing(**values)
            self._db.add(row)
            self._db.commit()
            return row, True

        # A listing we had ended is live again — relisted, or ended while we were not looking and
        # back since. It is active now, so the end has to be withdrawn with it; leaving `ended_at`
        # set would give the row an end date in its own past.
        if existing.status != "active" and values.get("status") == "active":
            existing.ended_at = None
            existing.sold_price_cents = None

        for key, value in values.items():
            if key in ("source_id", "external_id", "first_seen_at", "first_seen_run_id"):
                continue  # provenance of the first sighting is not rewritten by a later one
            setattr(existing, key, value)
        self._db.commit()
        return existing, False

    def due_for_recheck(
        self, source_id: str, *, older_than_hours: float, limit: int
    ) -> list[MarketListing]:
        """Live listings we have not looked at recently, oldest first.

        Oldest-first is the fairness rule: it guarantees every tracked listing is eventually
        re-checked, where newest-first would starve a long tail that never changes and is
        therefore never re-sorted.
        """
        cutoff = _utcnow() - timedelta(hours=older_than_hours)
        return list(self._db.scalars(
            select(MarketListing)
            .where(
                MarketListing.source_id == source_id,
                MarketListing.status == "active",
                MarketListing.last_seen_at < cutoff,
            )
            .order_by(MarketListing.last_seen_at)
            .limit(limit)
        ))

    def mark_seen(
        self,
        listing: MarketListing,
        *,
        run_id: str,
        at: datetime,
        price_cents: int | None = None,
        currency: str | None = None,
    ) -> None:
        listing.last_seen_at = at
        listing.last_seen_run_id = run_id
        if price_cents is not None:
            listing.price_cents = price_cents
        if currency:
            listing.currency = currency
        self._db.commit()

    def mark_ended(
        self,
        listing: MarketListing,
        *,
        status: str,
        at: datetime,
        sold_price_cents: int | None = None,
    ) -> None:
        """`status` is one of the three `ended_*` values. See `models/market_listing.py` for why
        `ended_sold` is not the default reading of a listing that disappeared."""
        listing.status = status
        listing.ended_at = at
        if sold_price_cents is not None:
            listing.sold_price_cents = sold_price_cents
        self._db.commit()

    def _listing_filter(
        self,
        stmt: Select,
        *,
        source_id: str | None,
        run_id: str | None,
        status: str | None,
        kind: str | None,
        matched: bool | None,
        min_confidence: float | None,
        max_confidence: float | None,
        search: str | None,
    ) -> Select:
        if source_id:
            stmt = stmt.where(MarketListing.source_id == source_id)
        if run_id:
            stmt = stmt.where(
                (MarketListing.first_seen_run_id == run_id)
                | (MarketListing.last_seen_run_id == run_id)
            )
        if status:
            stmt = stmt.where(MarketListing.status == status)
        if kind:
            stmt = stmt.where(MarketListing.kind == kind)
        if matched is True:
            stmt = stmt.where(
                MarketListing.printing_id.is_not(None)
                | MarketListing.sealed_product_id.is_not(None)
            )
        elif matched is False:
            stmt = stmt.where(
                MarketListing.printing_id.is_(None),
                MarketListing.sealed_product_id.is_(None),
            )
        if min_confidence is not None:
            stmt = stmt.where(MarketListing.match_confidence >= min_confidence)
        if max_confidence is not None:
            stmt = stmt.where(MarketListing.match_confidence < max_confidence)
        if search:
            stmt = stmt.where(MarketListing.title.like(f"%{search}%"))
        return stmt

    def list_listings(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        source_id: str | None = None,
        run_id: str | None = None,
        status: str | None = None,
        kind: str | None = None,
        matched: bool | None = None,
        min_confidence: float | None = None,
        max_confidence: float | None = None,
        search: str | None = None,
    ) -> list[MarketListing]:
        stmt = self._listing_filter(
            select(MarketListing), source_id=source_id, run_id=run_id, status=status, kind=kind,
            matched=matched, min_confidence=min_confidence, max_confidence=max_confidence,
            search=search,
        )
        return list(self._db.scalars(
            stmt.order_by(MarketListing.last_seen_at.desc(), MarketListing.id).limit(limit).offset(offset)
        ))

    def count_listings(
        self,
        *,
        source_id: str | None = None,
        run_id: str | None = None,
        status: str | None = None,
        kind: str | None = None,
        matched: bool | None = None,
        min_confidence: float | None = None,
        max_confidence: float | None = None,
        search: str | None = None,
    ) -> int:
        stmt = self._listing_filter(
            select(func.count(MarketListing.id)), source_id=source_id, run_id=run_id,
            status=status, kind=kind, matched=matched, min_confidence=min_confidence,
            max_confidence=max_confidence, search=search,
        )
        return int(self._db.scalar(stmt) or 0)

    def rejection_rollup(
        self, *, source_id: str | None = None, limit: int = 20
    ) -> list[tuple[str, int]]:
        """`(reason, count)` for listings that produced no observation, most common first.

        Grouped so an admin reads "83 × graded" rather than scrolling 83 rows — the same shape
        phase 1's import rejections take, for the same reason.

        The reason is the leading clause of `match_note`, which is written by the matcher as a
        stable phrase precisely so this grouping is possible without a second column.
        """
        stmt = (
            select(MarketListing.match_note, func.count(MarketListing.id))
            .where(MarketListing.match_note.is_not(None))
            .group_by(MarketListing.match_note)
            .order_by(func.count(MarketListing.id).desc())
            .limit(limit * 4)  # over-fetch: notes are grouped again in Python by their prefix
        )
        if source_id:
            stmt = stmt.where(MarketListing.source_id == source_id)

        grouped: dict[str, int] = {}
        for note, count in self._db.execute(stmt).all():
            reason = str(note).split(";")[0].split("—")[0].strip()
            grouped[reason] = grouped.get(reason, 0) + int(count)
        return sorted(grouped.items(), key=lambda kv: kv[1], reverse=True)[:limit]

    # --- what the light scan should look at next ------------------------------------

    def focus_labels(self, source_id: str, *, limit: int) -> list[tuple[str, str | None, str]]:
        """`(search text, kind hint, reason)` for the light plan's "more like this" queries.

        Two populations, in this order:

        1. **Products whose listing just ended.** Something left the market, so this is the moment
           a replacement is most likely to appear and least likely to be already known.
        2. **Products we have never had a live listing for.** Thin coverage.

        Products with several healthy live listings are deliberately absent: the light scan
        already re-checks those by id, and querying for more of what we are already tracking is
        the expensive half of a deep scan with none of its discovery.

        Returns ids rather than names — the caller resolves names through the catalog repository,
        keeping this query inside our own schema.
        """
        out: list[tuple[str, str | None, str]] = []
        seen: set[str] = set()

        ended = self._db.execute(
            select(MarketListing.printing_id, MarketListing.sealed_product_id)
            .where(
                MarketListing.source_id == source_id,
                MarketListing.status != "active",
                MarketListing.ended_at.is_not(None),
            )
            .order_by(MarketListing.ended_at.desc())
            .limit(limit * 2)
        ).all()
        for printing_id, sealed_id in ended:
            key = printing_id or sealed_id
            if not key or key in seen or len(out) >= limit:
                continue
            seen.add(key)
            out.append((
                key,
                "single" if printing_id else "sealed",
                "a listing for this product just ended",
            ))
        return out

    def products_with_live_listings(self, source_id: str) -> set[str]:
        rows = self._db.execute(
            select(MarketListing.printing_id, MarketListing.sealed_product_id).where(
                MarketListing.source_id == source_id, MarketListing.status == "active"
            )
        ).all()
        return {value for row in rows for value in row if value}

    # --- observations ---------------------------------------------------------------

    def record_observation(self, values: dict) -> bool:
        """Insert one price point, or do nothing if we already have it. Returns whether it was
        written.

        Insert-or-ignore against `UNIQUE (source_id, external_id)`: the whole idempotency story
        of a re-run lives in this one statement. See the module docstring for why it is not an
        upsert.
        """
        table = PriceObservation.__table__
        dialect = self._db.get_bind().dialect.name

        if dialect == "mysql":
            stmt = mysql_insert(table).values(**values).prefix_with("IGNORE")
        else:
            stmt = sqlite_insert(table).values(**values).on_conflict_do_nothing(
                index_elements=["source_id", "external_id"]
            )
        result = self._db.execute(stmt)
        self._db.commit()
        return bool(result.rowcount)

    def count_observations(self, *, run_id: str | None = None) -> int:
        stmt = select(func.count(PriceObservation.id))
        if run_id:
            stmt = stmt.where(PriceObservation.run_id == run_id)
        return int(self._db.scalar(stmt) or 0)

    def observation_days(self, *, since: date | None = None) -> list[date]:
        """Distinct days that have observations — the rollup's work list."""
        stmt = select(func.date(PriceObservation.observed_at)).distinct()
        if since:
            stmt = stmt.where(PriceObservation.observed_at >= since)
        values = [row[0] for row in self._db.execute(stmt).all() if row[0]]
        return sorted(
            v if isinstance(v, date) else date.fromisoformat(str(v)[:10]) for v in values
        )

    def observations_for_day(self, day: date) -> list[PriceObservation]:
        """Every observation stamped on one calendar day, excluded rows omitted.

        `is_excluded` is how a correction works — a new row plus a flag on the old one — so the
        rollup must not see the superseded value.
        """
        start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        return list(self._db.scalars(
            select(PriceObservation).where(
                PriceObservation.observed_at >= start,
                PriceObservation.observed_at < end,
                PriceObservation.is_excluded.is_(False),
            )
        ))

    def observations_for_product(
        self,
        *,
        printing_id: str | None = None,
        sealed_product_id: str | None = None,
        day: date | None = None,
        limit: int = 500,
    ) -> list[PriceObservation]:
        """The admin distribution view's query — every point behind a rollup."""
        stmt = select(PriceObservation).where(PriceObservation.is_excluded.is_(False))
        if printing_id:
            stmt = stmt.where(PriceObservation.printing_id == printing_id)
        if sealed_product_id:
            stmt = stmt.where(PriceObservation.sealed_product_id == sealed_product_id)
        if day:
            start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
            stmt = stmt.where(
                PriceObservation.observed_at >= start,
                PriceObservation.observed_at < start + timedelta(days=1),
            )
        return list(self._db.scalars(
            stmt.order_by(PriceObservation.observed_at.desc()).limit(limit)
        ))

    def mark_outliers(self, observation_ids: list[int], *, is_outlier: bool = True) -> None:
        """Flag, never delete. A silently dropped point is indistinguishable from one that never
        existed, which makes the rollup unauditable — and a source that suddenly produces many
        outliers is more likely broken than the market is to have gone strange."""
        if not observation_ids:
            return
        for obs in self._db.scalars(
            select(PriceObservation).where(PriceObservation.id.in_(observation_ids))
        ):
            obs.is_outlier = is_outlier
        self._db.commit()

    def printings_observed_since(self, since: datetime) -> set[str]:
        """Distinct printings with a `sold` observation in the window. Coverage's numerator."""
        rows = self._db.execute(
            select(PriceObservation.printing_id).distinct().where(
                PriceObservation.printing_id.is_not(None),
                PriceObservation.observed_at >= since,
                PriceObservation.sale_type == "sold",
                PriceObservation.is_excluded.is_(False),
            )
        ).all()
        return {row[0] for row in rows if row[0]}

    # --- rollups ---------------------------------------------------------------------

    def upsert_daily(self, values: dict) -> None:
        """Recompute a day in place. The rollup is a projection, never accumulated — which is
        what makes "run it again and get the same answer" true, and what makes a bug in it
        fixable by re-running rather than by a data migration."""
        table = PriceDaily.__table__
        dialect = self._db.get_bind().dialect.name
        keys = [
            "low_cents", "median_cents", "high_cents", "mean_cents", "observation_count",
            "source_count", "excluded_count", "confidence", "computed_at",
        ]

        # Derived here rather than by the caller: the key columns exist only to give the unique
        # constraint something non-null to hold on to, and nothing outside this method should
        # have to remember they are there.
        values = dict(values)
        values["product_key"] = values.get("printing_id") or values.get("sealed_product_id")
        values["product_kind"] = "printing" if values.get("printing_id") else "sealed"
        values["condition_key"] = values.get("condition") or ""

        if dialect == "mysql":
            stmt = mysql_insert(table).values(**values)
            stmt = stmt.on_duplicate_key_update(**{k: stmt.inserted[k] for k in keys})
        else:
            stmt = sqlite_insert(table).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=[
                    "product_key", "product_kind", "condition_key", "day", "currency",
                    "sale_type",
                ],
                set_={k: stmt.excluded[k] for k in keys},
            )
        self._db.execute(stmt)
        self._db.commit()

    def daily_for_product(
        self,
        *,
        printing_id: str | None = None,
        sealed_product_id: str | None = None,
        since: date | None = None,
        sale_type: str | None = None,
    ) -> list[PriceDaily]:
        stmt = select(PriceDaily)
        if printing_id:
            stmt = stmt.where(PriceDaily.printing_id == printing_id)
        if sealed_product_id:
            stmt = stmt.where(PriceDaily.sealed_product_id == sealed_product_id)
        if since:
            stmt = stmt.where(PriceDaily.day >= since)
        if sale_type:
            stmt = stmt.where(PriceDaily.sale_type == sale_type)
        return list(self._db.scalars(stmt.order_by(PriceDaily.day)))

    def latest_daily_by_printing(self, *, sale_type: str = "sold") -> dict[str, PriceDaily]:
        """The most recent rollup per printing. What the admin views summarise."""
        latest: dict[str, PriceDaily] = {}
        for row in self._db.scalars(
            select(PriceDaily)
            .where(PriceDaily.sale_type == sale_type, PriceDaily.printing_id.is_not(None))
            .order_by(PriceDaily.day)
        ):
            latest[row.printing_id] = row  # later days overwrite earlier ones
        return latest
