"""Scan tasks. Thin wrappers — the work lives in `HarvestRunner`.

Deliberately thin. Story 027 requires that the admin-triggered path and the scheduled path are
the same code; the way to guarantee that is for both to be three lines around
`make_harvest_runner`, with nothing that could drift living in here.
"""
from __future__ import annotations

from ..core.db import SessionLocal
from ..core.dependencies import make_harvest_runner
from ..harvest.gate import SourceNotCleared
from ..repositories.price_source_repository import PriceSourceRepository
from ..services.logging_service import log_event
from .celery_app import celery_app


@celery_app.task(name="harvest.scan", bind=True)
def run_scan(self, *, source_key: str, mode: str, run_id: str | None = None) -> dict:
    """Run one scan. `run_id` is set when an admin already created the row to get an id back."""
    db = SessionLocal()
    try:
        runner = make_harvest_runner(db)
        run = None
        if run_id:
            from ..repositories.harvest_repository import HarvestRepository

            run = HarvestRepository(db).get_run(run_id)
        result = runner.run(
            source_key=source_key,
            mode=mode,
            run=run,
            triggered_by="admin" if run_id else "schedule",
        )
        return {"run_id": result.id, "status": result.status}
    except SourceNotCleared as exc:
        # Not an error worth retrying: the gate refused, and it will refuse again in ten seconds.
        log_event(
            "warning", f"scan refused: {source_key}",
            component="tasks", operation="scan", context={"reason": str(exc)},
        )
        return {"run_id": run_id, "status": "refused", "reason": str(exc)}
    finally:
        db.close()


@celery_app.task(name="harvest.scan_all")
def scan_all(*, mode: str) -> dict:
    """Fan out one scan per enabled source.

    Queued individually rather than looped in one task, so one source failing, blocking or
    taking four hours does not hold up the others — FR-2's "a source failing does not fail the
    run for other sources", expressed in the runtime rather than in a try/except.
    """
    db = SessionLocal()
    try:
        keys = [row.key for row in PriceSourceRepository(db).list_enabled()]
    finally:
        db.close()

    for key in keys:
        run_scan.delay(source_key=key, mode=mode)
    return {"queued": len(keys), "mode": mode}
