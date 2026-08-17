"""`/api/v1/admin/maintenance` — recompute the rollup, and sweep orphaned runs, on demand.

**Why this exists.** A scan can already be started by hand, from two places: the CLI
(`python -m app.harvest --source ebay_sold --mode deep`) and the console's own Light/Deep buttons.
But a scan only writes observations. Nothing a *collector* sees moves until `price_daily` is
recomputed, and until now that only happened on the beat schedule — so someone who triggered a scan
to check a fix had to either wait out `HARVEST_ROLLUP_EVERY_MINUTES` or shell into the container.
That gap made the manual path useless for the thing it is most needed for: seeing whether a change
worked.

**Two decisions worth keeping.**

*The rollup runs inline, and is bounded.* Unlike a scan — hours long, so `202` and a run row to
poll — a rollup over recent days is seconds, and an admin pressing "recompute" wants the numbers,
not a task id with nowhere to look. Bounding it is what makes that safe: `since_days` is capped, so
this endpoint cannot become a synchronous full-history rebuild inside an HTTP request. A genuine
full rebuild stays where it belongs, with no cap and no request timeout — `--rollup` on the CLI, or
the beat schedule.

*Neither of these is destructive, and that is a property of the rollup rather than of the caller.*
`price_daily` is a projection: recomputing it is the fix for any bug in it, and running it twice is
the same as running it once. So there is no confirmation step here — there is nothing to confirm.
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..config import settings
from ..core.db import get_db
from ..core.dependencies import require_admin, rollup_service
from ..core.security import Principal
from ..repositories.harvest_repository import HarvestRepository
from ..schemas import RollupRun, SweepResult
from ..services.logging_service import log_event
from ..services.rollup_service import RollupService
from ..models.base import utc_today

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

#: The widest window this endpoint will recompute synchronously. Beyond it, use the CLI — a rebuild
#: over years of observations is a job, not a request, and pretending otherwise just moves the
#: timeout from something we control to something we do not.
MAX_SINCE_DAYS = 90


@router.post("/maintenance/rollup", response_model=RollupRun)
def recompute_rollup(
    since_days: int = Query(
        default=7, ge=1, le=MAX_SINCE_DAYS,
        description=("How many days back to recompute. Defaults to a week, which covers a scan "
                     f"that has just run. Capped at {MAX_SINCE_DAYS}: for a full rebuild use "
                     "`python -m app.harvest --rollup`."),
    ),
    principal: Principal = Depends(require_admin),
    rollups: RollupService = Depends(rollup_service),
) -> RollupRun:
    """Recompute `price_daily` for the last `since_days` days, now, and report what changed.

    The rollup is recomputed rather than accumulated, so every day in the window is rebuilt from
    its observations. A day whose observations arrived late, or whose outlier flags changed, is
    corrected by this — which is why the fix for a bad number is always to run it again rather
    than to patch a row.
    """
    # UTC, matching the day `price_daily` rows are stamped with. See `utc_today`.
    since = utc_today() - timedelta(days=since_days - 1)
    result = rollups.rebuild(since=since)

    log_event(
        "info", "rollup recomputed by admin",
        component="admin", operation="maintenance.rollup",
        context={"actor": principal.sub, "since": since.isoformat(), "since_days": since_days,
                 "days": result.days, "rows": result.rows, "excluded": result.excluded},
    )
    return RollupRun(
        since=since,
        since_days=since_days,
        days=result.days,
        rows=result.rows,
        excluded=result.excluded,
        max_since_days=MAX_SINCE_DAYS,
    )


@router.post("/maintenance/sweep", response_model=SweepResult)
def sweep_stale_runs(
    principal: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SweepResult:
    """Fail runs whose owning process is gone, without waiting for the ten-minute sweeper.

    The case this is for: a deploy or a killed worker leaves a run sitting `running`, and the
    duplicate-run refusal in `admin_runs` then blocks the very scan an admin is trying to start.
    Waiting out the schedule to unblock a manual trigger is exactly the friction this file exists
    to remove.
    """
    swept = HarvestRepository(db).sweep_stale(
        older_than_minutes=settings.harvest_run_stale_after_minutes
    )
    if swept:
        log_event(
            "warning", f"swept {swept} stale run(s) to failed, by admin",
            component="admin", operation="maintenance.sweep",
            context={"actor": principal.sub, "count": swept},
        )
    return SweepResult(
        swept=swept, stale_after_minutes=settings.harvest_run_stale_after_minutes
    )
