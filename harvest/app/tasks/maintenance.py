"""Maintenance tasks: the rollup, the stale-run sweeper, and the quarantine probe.

All three exist because something can be left in a wrong state by a process that is no longer
around to fix it — a crashed worker, a blocked source, a day whose observations arrived late.
"""
from __future__ import annotations

from ..config import settings
from ..core.db import SessionLocal
from ..core.dependencies import make_rollup_service
from ..harvest.gate import SourceNotCleared
from ..repositories.harvest_repository import HarvestRepository
from ..repositories.price_source_repository import PriceSourceRepository
from ..services.logging_service import log_event
from .celery_app import celery_app


@celery_app.task(name="harvest.rollup")
def rollup() -> dict:
    """Recompute `price_daily` from observations.

    Every day that has observations, not just today: a scan that arrives late, or a correction
    flagged on an old row, has to be able to change the past. The rollup is a projection, so
    recomputing is the fix for any bug in it.
    """
    db = SessionLocal()
    try:
        result = make_rollup_service(db).rebuild()
        log_event(
            "info", "rollup complete", component="rollup", operation="rebuild",
            context={"days": result.days, "rows": result.rows, "excluded": result.excluded},
        )
        return {"days": result.days, "rows": result.rows, "excluded": result.excluded}
    finally:
        db.close()


@celery_app.task(name="harvest.sweep")
def sweep() -> dict:
    """Fail runs whose owning process is gone (FR-2).

    Runs on a schedule *and* should be run at service startup: a deploy is the most common moment
    for a run to be orphaned.
    """
    db = SessionLocal()
    try:
        swept = HarvestRepository(db).sweep_stale(
            older_than_minutes=settings.harvest_run_stale_after_minutes
        )
        if swept:
            log_event(
                "warning", f"swept {swept} stale run(s) to failed",
                component="maintenance", operation="sweep", context={"count": swept},
            )
        return {"swept": swept}
    finally:
        db.close()


@celery_app.task(name="harvest.probe")
def probe_quarantined() -> dict:
    """One probing request per expired quarantine — never a full scan.

    Resuming a 400-query deep scan against a source that is still blocking would re-trigger
    whatever caused the block. So the probe is a light scan with the smallest possible plan: if
    it comes back clean the level resets, and if it refuses again the backoff doubles down.
    """
    db = SessionLocal()
    try:
        sources = PriceSourceRepository(db)
        due = sources.due_for_probe()
        probed = []
        for row in due:
            # Release first so the gate lets the probe through, but keep the escalation level —
            # if this fails, the next quarantine is longer, not the same length again.
            sources.clear_quarantine(row, reset_level=False)
            probed.append(row.key)
    finally:
        db.close()

    for key in probed:
        _probe_one.delay(source_key=key)
    return {"probed": probed}


@celery_app.task(name="harvest.probe_one")
def _probe_one(*, source_key: str) -> dict:
    from ..core.dependencies import make_harvest_runner

    db = SessionLocal()
    try:
        try:
            run = make_harvest_runner(db).run(
                source_key=source_key, mode="light", triggered_by="probe"
            )
        except SourceNotCleared as exc:
            return {"source": source_key, "status": "refused", "reason": str(exc)}
        # A clean probe clears the escalation; `_settle_quarantine` in the runner has already
        # decided that, so there is nothing to do here but report.
        return {"source": source_key, "status": run.status}
    finally:
        db.close()


@celery_app.task(name="harvest.drift")
def drift_check() -> dict:
    """Story 010's scheduled half. **Reports; never fails a build.**

    A connector breaking is silent by nature — zero rows looks exactly like a quiet market — so
    something has to go and look on purpose. This is that something, and it runs on a schedule
    rather than in CI because a third party being down must not fail a pull request.

    Only `drifted` and `unparseable` are logged at `error`. `empty`, `blocked` and `unreachable`
    are real states of the world that need no code change, and reporting them as drift is how the
    alert that matters gets ignored during the next outage.
    """
    from ..harvest.drift import check_source
    from ..harvest.sources import available_sources, describe_source, new_source
    from ..services.harvest_runner import default_client_factory

    reports = []
    db = SessionLocal()
    try:
        rows = {row.key: row for row in PriceSourceRepository(db).list_all() if row.enabled}
    finally:
        db.close()

    for key in available_sources():
        row = rows.get(key)
        if row is None:
            # A disabled source is not drifting, it is switched off. Checking it would make a
            # request ADR-004's gate exists to prevent, and report a policy decision as a bug.
            continue
        descriptor = describe_source(key)
        source = new_source(key)
        # Through the SAME client factory a real scan uses — its own rate limit, its own user
        # agent with the contact address, its own host pinning. A drift check that bypassed the
        # polite client would be an unrated request against a source we have promised to be
        # careful with, made once a day, forever.
        source.bind(default_client_factory(descriptor, row))
        report = check_source(source, reports_sold=descriptor.reports_sold)
        reports.append(report.as_dict())

        log_event(
            "error" if report.verdict.is_our_problem else "info",
            f"drift check: {report}",
            component="drift", operation="check",
            context=report.as_dict(),
        )

    if not reports:
        log_event(
            "info", "drift check: no enabled sources to check",
            component="drift", operation="check",
        )
    return {"checked": len(reports), "reports": reports}
