"""`/api/v1/admin/sources` — per-source health, and the kill switch.

Enabling a source is **not** here, and that is the unit brief's decision rather than an
oversight. Accepting a contractual risk is a deliberate act with a written note and a name
attached; putting it behind a button in a console makes it a click. The CLI requires both
arguments, and the schema refuses without them.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.dependencies import require_admin
from ..core.security import Principal
from ..harvest.sources import available_sources
from ..models.harvest_run import HarvestRun
from ..models.price_source import PriceSource
from ..repositories.harvest_repository import HarvestRepository
from ..repositories.price_source_repository import PriceSourceRepository
from ..schemas import RunSummary, SourceHealth
from ..services.logging_service import log_event

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/sources", response_model=list[SourceHealth])
def list_sources(
    _: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[SourceHealth]:
    sources = PriceSourceRepository(db)
    harvest = HarvestRepository(db)
    rows = sources.list_all()
    known = set(available_sources())

    out = []
    for row in rows:
        out.append(_to_health(row, harvest, has_connector=row.key in known))
    # A config row whose connector was deleted is a real state and must not be invisible: it
    # still looks configured from the database's point of view.
    for key in sorted(known - {r.key for r in rows}):
        out.append(SourceHealth(
            key=key, name=f"{key} (no config row)", access_mode="unknown", enabled=False,
            reports_sold=False, rate_limit_per_min=0, tos_review_note=None,
            risk_accepted_by=None, risk_accepted_on=None, quarantined=False,
            quarantined_until=None, quarantine_reason=None, quarantine_level=0,
        ))
    return out


@router.post("/sources/{key}/disable", response_model=SourceHealth)
def disable_source(
    key: str,
    principal: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SourceHealth:
    """The kill switch. Takes effect on the next scan, with no deploy and no restart."""
    sources = PriceSourceRepository(db)
    try:
        row = sources.disable(key)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "No such source", "details": {}}},
        ) from None
    log_event(
        "warning", f"source disabled by admin: {key}",
        component="admin", operation="source.disable",
        context={"source": key, "actor": principal.sub},
    )
    return _to_health(row, HarvestRepository(db), has_connector=True)


@router.post("/sources/{key}/clear-quarantine", response_model=SourceHealth)
def clear_quarantine(
    key: str,
    principal: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SourceHealth:
    """Override a quarantine deliberately.

    Exposed because an admin who knows the block was a false positive should not have to edit a
    row by hand — but logged at `warning`, because overriding FR-18's backoff is exactly the
    decision that turns a temporary block into a permanent one when it is wrong.
    """
    sources = PriceSourceRepository(db)
    row = sources.by_key(key)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "No such source", "details": {}}},
        )
    sources.clear_quarantine(row, reset_level=False)
    log_event(
        "warning", f"quarantine cleared by admin: {key}",
        component="admin", operation="source.clear-quarantine",
        context={"source": key, "actor": principal.sub, "level_kept": row.quarantine_level},
    )
    return _to_health(row, HarvestRepository(db), has_connector=True)


def _to_health(
    row: PriceSource, harvest: HarvestRepository, *, has_connector: bool
) -> SourceHealth:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    deep = harvest.latest_run(row.id, mode="deep")
    light = harvest.latest_run(row.id, mode="light")
    return SourceHealth(
        key=row.key,
        name=row.name if has_connector else f"{row.name} (no connector registered)",
        access_mode=row.access_mode,
        enabled=row.enabled,
        reports_sold=row.reports_sold,
        rate_limit_per_min=row.rate_limit_per_min,
        tos_review_note=row.tos_review_note,
        risk_accepted_by=row.risk_accepted_by,
        risk_accepted_on=row.risk_accepted_on,
        quarantined=row.is_quarantined(now),
        quarantined_until=row.quarantined_until,
        quarantine_reason=row.quarantine_reason,
        quarantine_level=row.quarantine_level,
        last_deep_run=_summary(deep, row.key),
        last_light_run=_summary(light, row.key),
        accept_rate_deep=_rate_points(harvest, row.id, "deep"),
        accept_rate_light=_rate_points(harvest, row.id, "light"),
        live_listings=harvest.count_listings(source_id=row.id, status="active"),
        never_run=deep is None and light is None,
    )


def _rate_points(harvest: HarvestRepository, source_id: str, mode: str):
    return [
        (started, (accepted / parsed) if parsed else 0.0)
        for started, parsed, accepted in harvest.accept_rate_trend(source_id, mode=mode)
    ]


def _summary(run: HarvestRun | None, source_key: str) -> RunSummary | None:
    if run is None:
        return None
    duration = (
        (run.finished_at - run.started_at).total_seconds() if run.finished_at else None
    )
    return RunSummary(
        id=run.id, source_key=source_key, mode=run.mode, status=run.status,
        triggered_by=run.triggered_by, started_at=run.started_at,
        finished_at=run.finished_at, duration_seconds=duration, queries=run.queries,
        fetched=run.fetched, parsed=run.parsed, accepted=run.accepted, rejected=run.rejected,
        discovered=run.discovered, ended=run.ended, error_summary=run.error_summary,
        stop_requested=run.stop_requested,
    )
