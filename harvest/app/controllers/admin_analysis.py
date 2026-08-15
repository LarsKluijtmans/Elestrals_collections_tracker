"""`/api/v1/admin/analysis` — is this data good enough to show anyone?

Bolt 015. Two views, and between them they are the reason unit 005 is scheduled before the
user-facing surfaces: under ADR-004 every figure comes from scraped pages of uneven quality, and
somebody has to look before a collector's portfolio number is built on them.

* **Coverage and match quality** — how much of the catalog we are pricing, how the accept rate is
  trending per source and per mode, and the rejection reasons grouped so the largest matcher gap
  is visible without reading rows. The unmatched queue is split into "no catalog card found" and
  "matched but under the floor", because those point at different work: the first at the catalog,
  the second at the matcher.
* **Distribution and source agreement** — every observation behind a rollup, with the excluded
  outliers drawn distinctly, and where two sources cover the same printing, how far apart they
  are. With no licensed reference to check against, cross-source comparison **is** the reference.
"""
from __future__ import annotations

import statistics
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.dependencies import require_admin
from ..core.security import Principal
from ..repositories.catalog_snapshot_repository import CatalogSnapshotRepository
from ..repositories.harvest_repository import HarvestRepository
from ..repositories.price_source_repository import PriceSourceRepository
from ..schemas import (
    CoverageReport, DistributionReport, MatchQuality, ObservationPoint, RejectionReason,
    SourceAgreement,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/analysis/coverage", response_model=CoverageReport)
def coverage(
    _: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
    window_days: int = Query(default=7, ge=1, le=365),
) -> CoverageReport:
    harvest = HarvestRepository(db)
    catalog = CatalogSnapshotRepository(db)
    sources = PriceSourceRepository(db)

    tracked = catalog.tracked_printing_ids()
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    priced = harvest.printings_observed_since(since)

    quality = []
    for row in sources.list_all():
        for mode in ("deep", "light"):
            points = [
                (started, (accepted / parsed) if parsed else 0.0)
                for started, parsed, accepted in harvest.accept_rate_trend(row.id, mode=mode)
            ]
            if points:
                quality.append(MatchQuality(source_key=row.key, mode=mode, points=points))

    return CoverageReport(
        tracked_printings=len(tracked),
        # The denominator is shown alongside on purpose: a high ratio over an incomplete catalog
        # is not the same achievement as a high ratio over a complete one, and ADR-001 left the
        # seed incomplete.
        priced_printings=len(priced & set(tracked)),
        window_days=window_days,
        match_quality=quality,
        top_rejections=[
            RejectionReason(reason=reason, count=count)
            for reason, count in harvest.rejection_rollup(limit=15)
        ],
        # The split that decides where the work is. "No catalog card found" is often a real
        # finding — a product the catalog is missing, which is one of the two things a deep scan
        # is for. "Under the floor" is a matcher gap, or a title that genuinely does not say
        # enough. Merging them into one "unmatched" number hides which you should be fixing.
        unmatched_no_catalog=harvest.count_listings(matched=False, kind="unknown"),
        unmatched_under_floor=harvest.count_listings(matched=True, max_confidence=0.70),
    )


@router.get("/analysis/distribution", response_model=DistributionReport)
def distribution(
    _: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
    printing_id: str | None = Query(default=None),
    sealed_product_id: str | None = Query(default=None),
    day: date | None = Query(default=None),
) -> DistributionReport:
    if not printing_id and not sealed_product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request",
                              "message": "printing_id or sealed_product_id is required",
                              "details": {}}},
        )

    harvest = HarvestRepository(db)
    sources = PriceSourceRepository(db)
    keys = {row.id: row.key for row in sources.list_all()}

    observations = harvest.observations_for_product(
        printing_id=printing_id, sealed_product_id=sealed_product_id, day=day
    )
    points = [
        ObservationPoint(
            id=obs.id,
            source_key=keys.get(obs.source_id, "?"),
            sale_type=obs.sale_type,
            observed_at=obs.observed_at,
            price_cents=obs.price_cents,
            currency=obs.currency,
            condition=obs.condition,
            is_outlier=obs.is_outlier,
            source_url=obs.source_url,
        )
        for obs in observations
    ]

    label = None
    if printing_id:
        resolved = CatalogSnapshotRepository(db).printing_labels([printing_id]).get(printing_id)
        if resolved:
            label = (
                f"{resolved['card']} · {resolved['set_code']} {resolved['collector_number']} "
                f"· {resolved['finish']}"
            )

    agreement = _agreement(points)
    return DistributionReport(
        printing_id=printing_id,
        sealed_product_id=sealed_product_id,
        product_label=label,
        day=day,
        points=points,
        agreement=agreement,
        # Stated rather than rendered as an empty comparison: single-source coverage is a fact
        # about confidence, not a gap in the view.
        single_source=len(agreement) <= 1,
    )


def _agreement(points: list[ObservationPoint]) -> list[SourceAgreement]:
    """Per-source medians and their signed distance from the cross-source median.

    Sold observations only, and outliers excluded — comparing sources on asking prices would
    measure how optimistic each marketplace's sellers are, which is a different question.
    """
    usable = [p for p in points if p.sale_type == "sold" and not p.is_outlier]
    if not usable:
        return []

    by_source: dict[str, list[int]] = {}
    for point in usable:
        by_source.setdefault(point.source_key, []).append(point.price_cents)

    overall = statistics.median([p.price_cents for p in usable])
    out = []
    for key, values in sorted(by_source.items()):
        median = int(statistics.median(values))
        out.append(SourceAgreement(
            source_key=key,
            median_cents=median,
            observation_count=len(values),
            delta_pct=round(((median - overall) / overall) * 100, 2) if overall else 0.0,
        ))
    return out
