"""All database access for `app_logs`. The only place that touches the table."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models.app_log import AppLog


class AppLogRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, entry: AppLog) -> AppLog:
        self._db.add(entry)
        self._db.commit()
        return entry

    def recent(self, *, limit: int = 100, level: str | None = None) -> list[AppLog]:
        stmt = select(AppLog).order_by(AppLog.at.desc()).limit(limit)
        if level:
            stmt = stmt.where(AppLog.level == level)
        return list(self._db.scalars(stmt))

    def sweep(self, *, now: datetime | None = None) -> int:
        """Retention: debug/info 30 days, warning and above 365 days."""
        now = now or datetime.now(timezone.utc)
        removed = 0
        low = self._db.execute(
            delete(AppLog).where(
                AppLog.level.in_(("debug", "info")), AppLog.at < now - timedelta(days=30)
            )
        )
        high = self._db.execute(
            delete(AppLog).where(
                AppLog.level.in_(("warning", "error", "critical")),
                AppLog.at < now - timedelta(days=365),
            )
        )
        removed = (low.rowcount or 0) + (high.rowcount or 0)
        self._db.commit()
        return removed
