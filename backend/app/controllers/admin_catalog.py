"""Operator view over catalog imports — story 009.

Read-only reporting plus a trigger. The console UI that renders this is story 034 in bolt 003;
the numbers it needs are already on the run-detail response, so that bolt builds a panel rather
than adding a query.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response

from ..core.db import SessionLocal
from ..core.dependencies import (
    catalog_import_repository,
    coverage_service,
    make_import_runner,
    require_operator,
)
from ..importer.sources import UnknownSource, get_source
from ..models.catalog_import import CatalogImport
from ..repositories.catalog_import_repository import CatalogImportRepository
from ..schemas import (
    CoverageModel,
    ErrorResponse,
    ImportCountsModel,
    ImportRunDetail,
    ImportRunSummary,
    PagedImportRuns,
    PagedRejections,
    RejectionModel,
    StartImportRequest,
)
from ..services.coverage_service import CoverageService
from ..services.logging_service import log_event

router = APIRouter(prefix="/api/v1/admin/catalog", tags=["admin:catalog"])

_REJECTION_PAGE = 100


def _err(status: int, code: str, message: str, **details) -> HTTPException:
    return HTTPException(status_code=status,
                         detail={"error": {"code": code, "message": message, "details": details}})


def _encode_cursor(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str | None) -> str | None:
    if not cursor:
        return None
    try:
        return base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        raise _err(400, "bad_request", "Malformed cursor") from None


def _counts(run: CatalogImport) -> ImportCountsModel:
    return ImportCountsModel(
        sets_seen=run.sets_seen,
        cards_added=run.cards_added,
        cards_updated=run.cards_updated,
        cards_unchanged=run.cards_unchanged,
        printings_added=run.printings_added,
        rejected=run.rejected,
    )


def _summary(run: CatalogImport) -> ImportRunSummary:
    return ImportRunSummary(
        id=run.id, source=run.source, status=run.status,
        started_at=run.started_at, finished_at=run.finished_at, counts=_counts(run),
    )


@router.get("/imports", response_model=PagedImportRuns, summary="List catalog import runs")
def list_imports(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    _: object = Depends(require_operator),
    repo: CatalogImportRepository = Depends(catalog_import_repository),
) -> PagedImportRuns:
    before_raw = _decode_cursor(cursor)
    before = datetime.fromisoformat(before_raw) if before_raw else None

    rows = repo.list_recent(limit=limit + 1, status=status, source=source, before=before)
    has_more = len(rows) > limit
    rows = rows[:limit]

    return PagedImportRuns(
        items=[_summary(r) for r in rows],
        next_cursor=_encode_cursor(rows[-1].started_at.isoformat()) if has_more and rows else None,
        total=repo.count_runs(status=status, source=source),
    )


@router.get(
    "/imports/{run_id}",
    response_model=ImportRunDetail,
    summary="One import run, with coverage and rejections",
    responses={404: {"model": ErrorResponse}},
)
def get_import(
    run_id: str,
    cursor: str | None = Query(default=None),
    _: object = Depends(require_operator),
    repo: CatalogImportRepository = Depends(catalog_import_repository),
    coverage: CoverageService = Depends(coverage_service),
) -> ImportRunDetail:
    run = repo.get(run_id)
    if run is None:
        raise _err(404, "import_run_not_found", "Import run not found", import_id=run_id)

    offset_raw = _decode_cursor(cursor)
    offset = int(offset_raw) if offset_raw and offset_raw.isdigit() else 0

    rows = repo.rejections_for(run_id, limit=_REJECTION_PAGE + 1, offset=offset)
    has_more = len(rows) > _REJECTION_PAGE
    rows = rows[:_REJECTION_PAGE]
    total = repo.count_rejections(run_id)

    # Coverage for whichever sets this run touched. Derived from the catalog as it stands, so
    # it stays honest even when read long after the run.
    reports: list[CoverageModel] = []
    for set_code in (run.set_codes or []):
        report = coverage.coverage(set_code)
        if report is not None:
            reports.append(CoverageModel(**report.as_dict()))

    return ImportRunDetail(
        **_summary(run).model_dump(),
        coverage=reports,
        error_summary=run.error_summary,
        rejections=PagedRejections(
            items=[
                RejectionModel(
                    source_ref=r.source_ref, reason_code=r.reason_code,
                    field=r.field, message=r.message, raw_record=r.raw_record,
                )
                for r in rows
            ],
            next_cursor=_encode_cursor(str(offset + _REJECTION_PAGE)) if has_more else None,
            total=total,
        ),
    )


@router.post(
    "/imports",
    response_model=ImportRunSummary,
    status_code=202,
    summary="Start a catalog import",
    responses={404: {"model": ErrorResponse}},
)
def start_import(
    body: StartImportRequest,
    background: BackgroundTasks,
    response: Response,
    _: object = Depends(require_operator),
    repo: CatalogImportRepository = Depends(catalog_import_repository),
) -> ImportRunSummary:
    try:
        get_source(body.source)
    except UnknownSource as exc:
        raise _err(404, "set_not_found", str(exc), source=body.source) from None

    # The row is created synchronously so the 202 can carry its id; the work happens after
    # the response, on its own session.
    run = repo.start(body.source)
    background.add_task(_execute, run.id, body.source, body.set_codes)
    response.headers["Location"] = f"/api/v1/admin/catalog/imports/{run.id}"
    return _summary(run)


def _execute(run_id: str, source: str, set_codes: list[str] | None) -> None:
    """Background execution. Owns its session — the request's is closed by now."""
    db = SessionLocal()
    try:
        runner = make_import_runner(db)
        run = db.get(CatalogImport, run_id)
        if run is None:  # pragma: no cover — the row was just written
            return
        runner.run(source_name=source, set_codes=set_codes, run=run)
    except Exception as exc:  # noqa: BLE001 — a background crash must still be visible
        log_event("critical", "catalog import crashed", component="importer",
                  operation="import.background", exc=exc, context={"import_id": run_id})
    finally:
        db.close()
