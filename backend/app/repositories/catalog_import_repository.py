"""All database access for `catalog_imports` and `import_rejections`."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.catalog_import import CatalogImport
from ..models.import_rejection import ImportRejection


class CatalogImportRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def start(self, source: str, set_codes: list[str] | None = None) -> CatalogImport:
        run = CatalogImport(source=source, status="running", set_codes=set_codes)
        self._db.add(run)
        self._db.commit()
        return run

    def record_targets(self, run: CatalogImport, set_codes: list[str]) -> CatalogImport:
        """Persist the resolved target list once the adapter has expanded it."""
        run.set_codes = list(set_codes)
        self._db.commit()
        return run

    def finish(
        self,
        run: CatalogImport,
        *,
        status: str,
        counts: dict[str, int],
        error_summary: str | None = None,
    ) -> CatalogImport:
        """Counters are written **once**, here, rather than incremented per row — a crash
        mid-run cannot leave a half-counted run that still claims success."""
        run.status = status
        run.finished_at = datetime.now(timezone.utc)
        for key, value in counts.items():
            setattr(run, key, value)
        run.error_summary = error_summary
        self._db.commit()
        return run

    def add_rejections(self, run_id: str, rejections: list[ImportRejection]) -> None:
        if not rejections:
            return
        self._db.add_all(rejections)
        self._db.commit()

    def get(self, run_id: str) -> CatalogImport | None:
        return self._db.get(CatalogImport, run_id)

    def list_recent(
        self,
        *,
        limit: int = 50,
        status: str | None = None,
        source: str | None = None,
        before: datetime | None = None,
    ) -> list[CatalogImport]:
        stmt = select(CatalogImport).order_by(CatalogImport.started_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(CatalogImport.status == status)
        if source:
            stmt = stmt.where(CatalogImport.source == source)
        if before:
            stmt = stmt.where(CatalogImport.started_at < before)
        return list(self._db.scalars(stmt))

    def count_runs(self, *, status: str | None = None, source: str | None = None) -> int:
        stmt = select(func.count(CatalogImport.id))
        if status:
            stmt = stmt.where(CatalogImport.status == status)
        if source:
            stmt = stmt.where(CatalogImport.source == source)
        return int(self._db.scalar(stmt) or 0)

    def latest_per_source(self) -> list[CatalogImport]:
        """The most recent run for each source that has ever run, in one query."""
        latest = (
            select(
                CatalogImport.source.label("source"),
                func.max(CatalogImport.started_at).label("started_at"),
            )
            .group_by(CatalogImport.source)
            .subquery()
        )
        return list(
            self._db.scalars(
                select(CatalogImport).join(
                    latest,
                    (CatalogImport.source == latest.c.source)
                    & (CatalogImport.started_at == latest.c.started_at),
                )
            )
        )

    def rejection_rollup(self, run_id: str) -> list[tuple[str, int, str]]:
        """`(reason_code, count, example_source_ref)`.

        Grouped so an operator reads "83 × unknown_rarity" rather than scrolling 83 rows.
        """
        rows = self._db.execute(
            select(
                ImportRejection.reason_code,
                func.count(ImportRejection.id),
                func.min(ImportRejection.source_ref),
            )
            .where(ImportRejection.import_id == run_id)
            .group_by(ImportRejection.reason_code)
            .order_by(func.count(ImportRejection.id).desc())
        ).all()
        return [(row[0], int(row[1]), row[2]) for row in rows]

    def rejections_for(
        self, run_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[ImportRejection]:
        return list(
            self._db.scalars(
                select(ImportRejection)
                .where(ImportRejection.import_id == run_id)
                .order_by(ImportRejection.created_at, ImportRejection.id)
                .limit(limit)
                .offset(offset)
            )
        )

    def count_rejections(self, run_id: str) -> int:
        return int(
            self._db.scalar(
                select(func.count(ImportRejection.id)).where(
                    ImportRejection.import_id == run_id
                )
            )
            or 0
        )
