"""Observations → `price_daily`. The projection everything downstream reads.

Three rules carry the whole story:

* **Recomputed, never accumulated.** A rollup that increments cannot be fixed by re-running, and
  any bug in it becomes a data migration. This one rebuilds a day from its observations every
  time, so `upsert_daily` overwrites and running it twice is a no-op.
* **Outliers are flagged, not deleted.** Beyond 3× the interquartile range a point stops counting
  toward median and mean — and is marked `is_outlier` so the admin distribution view can draw it.
  A silently dropped point is indistinguishable from one that never existed, which makes the
  whole table unauditable, and a source that suddenly produces many outliers is far more likely
  broken than the market is to have gone strange.
* **`sold` and `listed` never mix.** They roll up into separate rows. A card can have both; the
  UI picks which to show and labels it, and valuation reads `sold` only.

The confidence rule is the requirements' verbatim, implemented once here rather than in each
chart: `high` = ≥ 5 sold from ≥ 2 sources, `medium` = ≥ 2 sold, `low` = anything else **including
anything derived from `listed` prices**, however many there are. An asking price is not evidence
of a transaction no matter how many people are asking.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone

from ..config import settings
from ..models.price_observation import PriceObservation
from ..repositories.harvest_repository import HarvestRepository


@dataclass(frozen=True, slots=True)
class RollupKey:
    printing_id: str | None
    sealed_product_id: str | None
    condition: str | None
    currency: str
    sale_type: str


@dataclass
class RollupResult:
    days: int = 0
    rows: int = 0
    excluded: int = 0


def split_outliers(
    values: list[int], *, factor: float, min_points: int
) -> tuple[list[int], list[int]]:
    """`(kept, excluded)` by the 3×IQR rule.

    IQR rather than standard deviations: card prices are not normally distributed, and a
    standard-deviation rule on a skewed distribution trims the wrong tail.

    Below `min_points` nothing is excluded — an interquartile range over three points is not a
    statistic, and applying one would drop half the data and call the rest confident.
    """
    if len(values) < min_points:
        return list(values), []

    ordered = sorted(values)
    q1, q3 = _quartiles(ordered)
    spread = q3 - q1
    if spread <= 0:
        return list(values), []  # every value identical; nothing is an outlier

    low, high = q1 - factor * spread, q3 + factor * spread
    kept = [v for v in values if low <= v <= high]
    excluded = [v for v in values if v < low or v > high]
    return kept, excluded


def _quartiles(ordered: list[int]) -> tuple[float, float]:
    mid = len(ordered) // 2
    lower = ordered[:mid]
    upper = ordered[mid + 1:] if len(ordered) % 2 else ordered[mid:]
    return statistics.median(lower or ordered), statistics.median(upper or ordered)


def confidence_for(*, sale_type: str, observations: int, sources: int) -> str:
    """The requirements' rule, in one place.

    `listed` is `low` by definition — the number of people asking a price says nothing about
    whether anyone paid it.
    """
    if sale_type != "sold":
        return "low"
    if observations >= 5 and sources >= 2:
        return "high"
    if observations >= 2:
        return "medium"
    return "low"


class RollupService:
    def __init__(self, *, harvest: HarvestRepository) -> None:
        self._harvest = harvest

    def rebuild(self, *, since: date | None = None) -> RollupResult:
        """Recompute every day that has observations. Safe to run as often as you like."""
        result = RollupResult()
        for day in self._harvest.observation_days(since=since):
            rows, excluded = self.rebuild_day(day)
            result.days += 1
            result.rows += rows
            result.excluded += excluded
        return result

    def rebuild_day(self, day: date) -> tuple[int, int]:
        """Recompute one day. Returns `(rows written, points excluded)`."""
        observations = self._harvest.observations_for_day(day)
        grouped: dict[RollupKey, list[PriceObservation]] = defaultdict(list)
        for obs in observations:
            grouped[RollupKey(
                printing_id=obs.printing_id,
                sealed_product_id=obs.sealed_product_id,
                condition=obs.condition,
                currency=obs.currency,
                sale_type=obs.sale_type,
            )].append(obs)

        rows = 0
        excluded_total = 0
        now = datetime.now(timezone.utc)

        for key, points in grouped.items():
            values = [p.price_cents for p in points]
            kept, excluded = split_outliers(
                values,
                factor=settings.harvest_outlier_iqr_factor,
                min_points=settings.harvest_outlier_min_points,
            )
            if not kept:
                continue

            # Flag the excluded points so the admin distribution view can draw them, and clear
            # the flag on the ones that survived — a re-run after a correction must be able to
            # un-flag a point that is no longer an outlier.
            excluded_set = _multiset(excluded)
            outlier_ids, kept_ids = [], []
            for point in points:
                if excluded_set.get(point.price_cents):
                    excluded_set[point.price_cents] -= 1
                    outlier_ids.append(point.id)
                else:
                    kept_ids.append(point.id)
            self._harvest.mark_outliers(outlier_ids, is_outlier=True)
            self._harvest.mark_outliers(kept_ids, is_outlier=False)

            kept_points = [p for p in points if p.id in set(kept_ids)]
            sources = {p.source_id for p in kept_points}

            self._harvest.upsert_daily({
                "printing_id": key.printing_id,
                "sealed_product_id": key.sealed_product_id,
                "condition": key.condition,
                "day": day,
                "currency": key.currency,
                "sale_type": key.sale_type,
                "low_cents": min(kept),
                "median_cents": int(statistics.median(kept)),
                "high_cents": max(kept),
                "mean_cents": int(statistics.fmean(kept)),
                # Counts what was **kept**, so confidence is computed on the data actually used
                # rather than on what happened to arrive.
                "observation_count": len(kept),
                "source_count": len(sources),
                "excluded_count": len(excluded),
                "confidence": confidence_for(
                    sale_type=key.sale_type, observations=len(kept), sources=len(sources)
                ),
                "computed_at": now,
            })
            rows += 1
            excluded_total += len(excluded)
        return rows, excluded_total


def _multiset(values: list[int]) -> dict[int, int]:
    out: dict[int, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return out
