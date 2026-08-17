"""The Celery application and its beat schedule.

One queue per **source class** rather than per source, so adding a source does not add
infrastructure. Sources are assigned to a class in config; a slow or quarantined source delays
only its own class.

Schedules live here but their cadences come from settings, because how often to read someone
else's site is an operational decision and should not need a deploy.

**Idempotency is owned by the run row and the dedupe keys, not by the queue.** A task delivered
twice must produce one run's worth of data, and that property comes from
`UNIQUE (source_id, external_id)` on listings and observations — not from exactly-once delivery,
which Redis does not offer and Celery does not promise.
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import schedule

from ..config import settings

celery_app = Celery(
    "harvest",
    broker=settings.harvest_redis_url,
    backend=settings.harvest_redis_url,
    include=["app.tasks.scans", "app.tasks.maintenance", "app.tasks.fx"],
)

celery_app.conf.update(
    task_acks_late=True,
    # A scan is long and not safe to run twice concurrently for one source; the duplicate-run
    # refusal in `admin_runs` and `running_run()` is what enforces that, and losing a task to a
    # worker crash is preferable to running two.
    worker_prefetch_multiplier=1,
    task_default_queue="scans",
    task_routes={
        "harvest.scan": {"queue": "scans"},
        "harvest.rollup": {"queue": "maintenance"},
        "harvest.sweep": {"queue": "maintenance"},
        "harvest.probe": {"queue": "maintenance"},
        "harvest.fx": {"queue": "maintenance"},
        "harvest.drift": {"queue": "maintenance"},
    },
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "light-scan-all": {
        "task": "harvest.scan_all",
        "schedule": schedule(run_every=settings.harvest_light_every_minutes * 60),
        "kwargs": {"mode": "light"},
    },
    "deep-scan-all": {
        "task": "harvest.scan_all",
        "schedule": schedule(run_every=settings.harvest_deep_every_minutes * 60),
        "kwargs": {"mode": "deep"},
    },
    "rollup": {
        "task": "harvest.rollup",
        "schedule": schedule(run_every=settings.harvest_rollup_every_minutes * 60),
    },
    # Runs often: a run orphaned by a deploy should not sit `running` until the next rollup.
    "sweep-stale-runs": {
        "task": "harvest.sweep",
        "schedule": schedule(run_every=600),
    },
    # FR-18's release path. One probing request per expired quarantine, never a full scan.
    "probe-quarantined": {
        "task": "harvest.probe",
        "schedule": schedule(run_every=900),
    },
    # Story 018: **one call a day.** Conversion is a join against `fx_rates`, never a request-path
    # call to a provider — so this is the only thing in the system that talks to one, and a
    # provider outage degrades tomorrow's precision rather than today's availability.
    "fx-rates": {
        "task": "harvest.fx",
        "schedule": schedule(run_every=86_400),
    },
    # Story 010. Daily, and deliberately NOT in CI: a connector breaking is silent by nature, so
    # something has to go and look — but a third party being down must not fail a pull request.
    "drift-check": {
        "task": "harvest.drift",
        "schedule": schedule(run_every=86_400),
    },
}
