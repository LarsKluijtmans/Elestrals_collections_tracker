"""`/api/v1/health` — the one unauthenticated route on this service.

Reports MySQL and Redis **separately**. A single boolean would make a partial outage look like a
total one, and the two failures have different consequences: without MySQL nothing works, without
Redis the API still answers and only scheduled work stops.
"""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from ..config import settings
from ..core.db import SessionLocal

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
def health() -> dict:
    return {
        "service": settings.app_name,
        "version": "0.1.0",
        "environment": settings.environment,
        "database": _database_ok(),
        "redis": _redis_ok(),
        # Surfaced deliberately. Someone reading a health check should be able to see the
        # conduct posture this service is running under without reading an ADR.
        "conduct": {
            "obeys_robots_txt": settings.harvest_obey_robots,
            "identified": bool(settings.harvest_contact_email.strip()),
        },
    }


def _database_ok() -> bool:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 — a health check reports, it does not raise
        return False


def _redis_ok() -> bool:
    try:
        import redis  # imported lazily: the API serves without it, only scans need it

        redis.Redis.from_url(settings.harvest_redis_url, socket_timeout=2).ping()
        return True
    except Exception:  # noqa: BLE001
        return False
