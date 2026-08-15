"""`/api/v1/admin/listings` — the explorer.

The surface the whole "admin-only raw data" decision exists for. Everything else in the console
supports this: it is where a human finds out whether the scrapers are producing something worth
building a valuation on.

Two things it is careful about:

* **`ended_unknown` is labelled as what it is.** The API returns the raw status and the UI renders
  "ended, reason unknown". Describing it loosely as sold would undo, in a label, the invariant
  chain that runs from the connector through the runner to the fact table.
* **Product names are resolved in a second pass.** The listing query stays inside
  `elestrals_harvest`; the catalog join happens afterwards, for one page of rows. Putting a
  cross-schema join in the hot query would make the service boundary load-bearing for
  performance, which is the fastest route to someone widening it.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.dependencies import require_admin
from ..core.security import Principal
from ..repositories.catalog_snapshot_repository import CatalogSnapshotRepository
from ..repositories.harvest_repository import HarvestRepository
from ..repositories.price_source_repository import PriceSourceRepository
from ..schemas import ListingSummary, PagedListings

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/listings", response_model=PagedListings)
def list_listings(
    _: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
    source: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    listing_status: str | None = Query(default=None, alias="status"),
    kind: str | None = Query(default=None, pattern="^(single|sealed|lot|unknown)$"),
    matched: bool | None = Query(default=None),
    min_confidence: float | None = Query(default=None, ge=0, le=1),
    max_confidence: float | None = Query(default=None, ge=0, le=1),
    search: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> PagedListings:
    harvest = HarvestRepository(db)
    sources = PriceSourceRepository(db)
    keys = {row.id: row.key for row in sources.list_all()}

    source_id = None
    if source:
        row = sources.by_key(source)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "not_found", "message": "No such source",
                                  "details": {}}},
            )
        source_id = row.id

    filters = dict(
        source_id=source_id, run_id=run_id, status=listing_status, kind=kind, matched=matched,
        min_confidence=min_confidence, max_confidence=max_confidence, search=search,
    )
    rows = harvest.list_listings(limit=limit, offset=offset, **filters)
    total = harvest.count_listings(**filters)

    labels = _labels(db, [r.printing_id for r in rows if r.printing_id])
    return PagedListings(
        items=[_to_summary(row, keys.get(row.source_id, "?"), labels) for row in rows],
        total=total,
    )


@router.get("/listings/{listing_id}", response_model=ListingSummary)
def get_listing(
    listing_id: str,
    _: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ListingSummary:
    harvest = HarvestRepository(db)
    row = harvest.get_listing(listing_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "No such listing", "details": {}}},
        )
    sources = PriceSourceRepository(db)
    source = sources.get(row.source_id)
    labels = _labels(db, [row.printing_id] if row.printing_id else [])
    return _to_summary(row, source.key if source else "?", labels)


def _labels(db: Session, printing_ids: list[str]) -> dict[str, str]:
    if not printing_ids:
        return {}
    raw = CatalogSnapshotRepository(db).printing_labels(printing_ids)
    return {
        pid: f"{v['card']} · {v['set_code']} {v['collector_number']} · {v['finish']}"
        for pid, v in raw.items()
    }


def _to_summary(row, source_key: str, labels: dict[str, str]) -> ListingSummary:
    return ListingSummary(
        id=row.id,
        source_key=source_key,
        external_id=row.external_id,
        title=row.title,
        url=row.url,
        image_url=row.image_url,
        kind=row.kind,
        status=row.status,
        price_cents=row.price_cents,
        currency=row.currency,
        shipping_cents=row.shipping_cents,
        quantity=row.quantity,
        buying_format=row.buying_format,
        location_country=row.location_country,
        printing_id=row.printing_id,
        sealed_product_id=row.sealed_product_id,
        condition=row.condition,
        match_confidence=float(row.match_confidence) if row.match_confidence is not None else None,
        match_note=row.match_note,
        # `None` when the catalog no longer has this printing — shown as unmatched rather than
        # as a broken row, which is the honest reading of "the catalog changed under us".
        product_label=labels.get(row.printing_id) if row.printing_id else None,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        ended_at=row.ended_at,
        sold_price_cents=row.sold_price_cents,
    )
