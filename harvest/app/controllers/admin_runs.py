"""`/api/v1/admin/runs` — run history, and starting or stopping a scan.

Story 027 in three decisions:

* **The trigger returns immediately with a run id.** `202 Accepted`, matching the phase-1 admin
  import endpoint. The run row is created synchronously so the id is real before the response
  returns; the work is queued.
* **A duplicate is refused, not queued.** `409`. Silently queueing makes an admin press the
  button twice, wonder why nothing happened, and get two runs an hour apart.
* **Stopping sets a flag the scan checks between queries.** It stops at a clean boundary and
  finishes its own run row. Killing the worker would also stop it, and would leave a `running`
  row for the sweeper to mislabel.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.dependencies import require_admin
from ..core.security import Principal
from ..harvest.sources import UnknownSource, describe_source
from ..repositories.harvest_repository import HarvestRepository
from ..repositories.price_source_repository import PriceSourceRepository
from ..schemas import PagedRuns, RunSummary, TriggerAccepted
from ..services.logging_service import log_event

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/runs", response_model=PagedRuns)
def list_runs(
    _: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
    source: str | None = Query(default=None),
    mode: str | None = Query(default=None, pattern="^(deep|light)$"),
    run_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> PagedRuns:
    harvest = HarvestRepository(db)
    sources = PriceSourceRepository(db)
    keys = {row.id: row.key for row in sources.list_all()}

    source_id = None
    if source:
        row = sources.by_key(source)
        if row is None:
            raise _not_found("No such source")
        source_id = row.id

    runs = harvest.list_runs(
        limit=limit, offset=offset, source_id=source_id, mode=mode, status=run_status
    )
    return PagedRuns(
        items=[_summary(run, keys.get(run.source_id, "?")) for run in runs],
        total=len(runs),
    )


@router.get("/runs/{run_id}", response_model=RunSummary)
def get_run(
    run_id: str,
    _: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RunSummary:
    """The live-counter endpoint. Polled while a scan runs — the run row is the source of truth,
    so a poll that lands after the scan finished returns the final status rather than missing an
    event, which is why this is polling and not a websocket."""
    harvest = HarvestRepository(db)
    run = harvest.get_run(run_id)
    if run is None:
        raise _not_found("No such run")
    sources = PriceSourceRepository(db)
    row = sources.get(run.source_id)
    return _summary(run, row.key if row else "?")


@router.post("/sources/{key}/scan/{mode}", response_model=TriggerAccepted, status_code=202)
def trigger_scan(
    key: str,
    mode: str,
    response: Response,
    principal: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TriggerAccepted:
    if mode not in ("deep", "light"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request",
                              "message": "mode must be 'deep' or 'light'", "details": {}}},
        )

    sources = PriceSourceRepository(db)
    row = sources.by_key(key)
    if row is None:
        raise _not_found("No such source")

    try:
        describe_source(key)
    except UnknownSource:
        raise _not_found("No connector registered for this source") from None

    harvest = HarvestRepository(db)
    if harvest.running_run(row.id, mode) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {
                "code": "conflict",
                "message": f"A {mode} scan is already running for {key}",
                "details": {"source": key, "mode": mode},
            }},
        )

    run = harvest.start_run(row.id, mode, triggered_by="admin")
    log_event(
        "info", f"scan triggered by admin: {key} ({mode})",
        component="admin", operation="run.trigger", run_id=run.id,
        context={"source": key, "mode": mode, "actor": principal.sub},
    )

    # Queued rather than run inline: a deep scan is a four-hour job and this is an HTTP request.
    # The import is local so the API serves even when Redis is unreachable — the failure then is
    # this one endpoint, not the whole service.
    from ..tasks.scans import run_scan

    try:
        run_scan.delay(source_key=key, mode=mode, run_id=run.id)
    except Exception as exc:  # noqa: BLE001 — a broker outage must not leave a phantom run
        harvest.finish_run(
            run, status="failed", counts={},
            error_summary=f"could not queue the scan: {type(exc).__name__}: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "unavailable",
                              "message": "Could not queue the scan; the job broker is down",
                              "details": {}}},
        ) from exc

    response.headers["Location"] = f"/api/v1/admin/runs/{run.id}"
    return TriggerAccepted(run_id=run.id, source_key=key, mode=mode, status=run.status)


@router.post("/runs/{run_id}/stop", response_model=RunSummary)
def stop_run(
    run_id: str,
    principal: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RunSummary:
    harvest = HarvestRepository(db)
    run = harvest.get_run(run_id)
    if run is None:
        raise _not_found("No such run")
    if run.status != "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "conflict", "message": "That run is not running",
                              "details": {"status": run.status}}},
        )
    harvest.request_stop(run)
    log_event(
        "warning", "scan stop requested by admin",
        component="admin", operation="run.stop", run_id=run.id,
        context={"actor": principal.sub},
    )
    sources = PriceSourceRepository(db)
    row = sources.get(run.source_id)
    return _summary(run, row.key if row else "?")


def _not_found(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "not_found", "message": message, "details": {}}},
    )


def _summary(run, source_key: str) -> RunSummary:
    duration = (run.finished_at - run.started_at).total_seconds() if run.finished_at else None
    return RunSummary(
        id=run.id, source_key=source_key, mode=run.mode, status=run.status,
        triggered_by=run.triggered_by, started_at=run.started_at, finished_at=run.finished_at,
        duration_seconds=duration, queries=run.queries, fetched=run.fetched, parsed=run.parsed,
        accepted=run.accepted, rejected=run.rejected, discovered=run.discovered,
        ended=run.ended, error_summary=run.error_summary, stop_requested=run.stop_requested,
    )
