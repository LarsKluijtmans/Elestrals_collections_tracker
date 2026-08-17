"""`/api/v1/export/*` and `/api/v1/import/*` — bolt 008, the anti-lock-in bolt.

Export is a **streaming** response: rows are generated, never accumulated. Ten thousand rows built
into a list and joined is a few hundred megabytes of Python strings for a file the user opens once,
and the NFR bounds this at 100MB RSS.

Import is three steps and the middle one is the point: upload → **dry run** → commit. The dry run
writes `import_jobs` and `import_rows` and touches the collection not at all, so a mis-mapped column
produces visible nonsense in a diff rather than an invisible mess in somebody's collection.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ..core.dependencies import (
    collection_browse_service,
    current_principal,
    import_service,
    inventory_repository,
    sealed_service,
    wishlist_service,
)
from ..repositories.inventory_repository import InventoryRepository
from ..schemas import (
    CommitResultResponse,
    ErrorResponse,
    ImportConfirmRequest,
    ImportJobResponse,
    ImportMappingRequest,
    ImportRowModel,
)
from ..security import Principal
from ..services.collection_browse_service import CollectionBrowseService
from ..services.collection_filters import FilterSet, InvalidFilter
from ..services.export_service import ExportService
from ..services.import_service import ImportService
from ..services.inventory_service import InventoryError
from ..services.sealed_service import SealedService
from ..services.wishlist_service import WishlistService

router = APIRouter(prefix="/api/v1", tags=["import-export"])

#: The dry run keeps the whole file's verdicts, but a response carrying 20,000 rows is not a
#: response anyone can render. The UI pages through the rejections, which are what it needs.
ROWS_IN_RESPONSE = 200


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status,
                         detail={"error": {"code": code, "message": message, "details": {}}})


def _as_error(exc: InventoryError) -> HTTPException:
    return _err(exc.status, exc.code, str(exc) or exc.code)


def _csv_response(lines, filename: str) -> StreamingResponse:
    return StreamingResponse(
        # A BOM, so Excel reads UTF-8 rather than the system codepage — otherwise a card called
        # "Pyrofrost Éclair" arrives as mojibake, which reads as our data being wrong.
        (chunk for chunk in ("﻿", *lines)),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- export --------------------------------------------------------------------------


@router.get("/export/collection", summary="Export singles as CSV, honouring the active filter")
def export_collection(
    request_filters: str | None = None,
    principal: Principal = Depends(current_principal),
    items: InventoryRepository = Depends(inventory_repository),
    _browse: CollectionBrowseService = Depends(collection_browse_service),
) -> StreamingResponse:
    """Story 027. The filter is honoured, so "export what I am looking at" is one action.

    The query string is the same vocabulary `/collection` uses — `FilterSet` again — so the link
    in the address bar and the file that comes out describe the same rows.
    """
    del _browse  # wired for symmetry with the other collection routes; the repo is enough here
    try:
        filters = FilterSet.from_params(_query_dict(request_filters))
    except InvalidFilter as exc:
        raise _err(400, "bad_request", str(exc)) from None

    rows = items.browse(principal.sub, filters, sort="added_desc", limit=100_000)
    return _csv_response(ExportService().singles(rows), "elestrals-collection.csv")


@router.get("/export/sealed", summary="Export sealed holdings as CSV")
def export_sealed(
    principal: Principal = Depends(current_principal),
    svc: SealedService = Depends(sealed_service),
) -> StreamingResponse:
    return _csv_response(
        ExportService().sealed(svc.list_for_user(principal.sub)), "elestrals-sealed.csv",
    )


@router.get("/export/wishlist", summary="Export the wishlist as CSV")
def export_wishlist(
    principal: Principal = Depends(current_principal),
    svc: WishlistService = Depends(wishlist_service),
) -> StreamingResponse:
    return _csv_response(
        ExportService().wishlist(svc.list_for_user(principal.sub)), "elestrals-wishlist.csv",
    )


# --- import --------------------------------------------------------------------------


def _job_view(job, *, include_rows: bool = True) -> ImportJobResponse:
    rows = []
    if include_rows:
        # Rejections and things needing confirmation first — they are what the user has to act
        # on, and a diff that buries them under 4,000 clean rows is a diff nobody reads.
        ordered = sorted(
            job.rows,
            key=lambda r: (r.verdict not in ("rejected", "needs_confirmation"), r.line_number),
        )
        rows = [
            ImportRowModel(
                id=r.id, line_number=r.line_number, verdict=r.verdict,
                match_rung=r.match_rung, match_score=r.match_score,
                printing_id=r.printing_id, quantity=r.quantity, condition=r.condition,
                reason=r.reason, confirmed=r.confirmed, raw=r.raw,
            )
            for r in ordered[:ROWS_IN_RESPONSE]
        ]

    return ImportJobResponse(
        id=job.id, filename=job.filename, status=job.status,
        encoding=job.encoding, delimiter=job.delimiter, mapping=job.mapping,
        total_rows=job.total_rows, add_count=job.add_count, update_count=job.update_count,
        needs_confirmation_count=job.needs_confirmation_count,
        rejected_count=job.rejected_count, error_summary=job.error_summary,
        rows=rows, rows_truncated=len(job.rows) > ROWS_IN_RESPONSE,
        created_at=job.created_at,
    )


@router.post(
    "/import", response_model=ImportJobResponse, status_code=201,
    summary="Upload a CSV and dry-run it — writes nothing to the collection",
    responses={400: {"model": ErrorResponse}},
)
async def start_import(
    file: UploadFile = File(...),
    principal: Principal = Depends(current_principal),
    svc: ImportService = Depends(import_service),
) -> ImportJobResponse:
    """**Nothing reaches the collection here.** The upload is parsed, a mapping is suggested, every
    row is resolved against the catalog, and the verdicts are stored — all of which is `import_*`
    state, none of which is inventory."""
    raw = await file.read()
    try:
        job = svc.start(principal.sub, filename=file.filename or "upload.csv", raw=raw)
    except InventoryError as exc:
        raise _as_error(exc) from None
    return _job_view(job)


@router.get("/import", response_model=list[ImportJobResponse])
def list_imports(
    principal: Principal = Depends(current_principal),
    svc: ImportService = Depends(import_service),
) -> list[ImportJobResponse]:
    """Story 028: leaving the page must not lose the job. A 5,000-row dry run is not something to
    make somebody sit through twice because they went to check a spreadsheet."""
    return [_job_view(job, include_rows=False) for job in svc.list_for_user(principal.sub)]


@router.get(
    "/import/{job_id}", response_model=ImportJobResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_import(
    job_id: str,
    principal: Principal = Depends(current_principal),
    svc: ImportService = Depends(import_service),
) -> ImportJobResponse:
    try:
        return _job_view(svc.get(principal.sub, job_id))
    except InventoryError as exc:
        raise _as_error(exc) from None


@router.put(
    "/import/{job_id}/mapping", response_model=ImportJobResponse,
    summary="Change the column mapping and re-run the dry run",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
               409: {"model": ErrorResponse}},
)
def remap_import(
    job_id: str,
    body: ImportMappingRequest,
    principal: Principal = Depends(current_principal),
    svc: ImportService = Depends(import_service),
) -> ImportJobResponse:
    try:
        return _job_view(svc.remap(principal.sub, job_id, body.mapping))
    except InventoryError as exc:
        raise _as_error(exc) from None


@router.post(
    "/import/{job_id}/confirm", response_model=ImportJobResponse,
    summary="Accept specific fuzzy matches, one by one",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def confirm_rows(
    job_id: str,
    body: ImportConfirmRequest,
    principal: Principal = Depends(current_principal),
    svc: ImportService = Depends(import_service),
) -> ImportJobResponse:
    """Takes a list of row ids the user actually ticked.

    Deliberately not a "confirm all" — that would collapse rung 4 into one click somebody makes
    without reading, which is the failure the whole ladder exists to prevent.
    """
    try:
        return _job_view(svc.confirm_rows(principal.sub, job_id, body.row_ids))
    except InventoryError as exc:
        raise _as_error(exc) from None


@router.post(
    "/import/{job_id}/commit", response_model=CommitResultResponse,
    summary="Apply the import — one transaction, all or nothing",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
               409: {"model": ErrorResponse}},
)
def commit_import(
    job_id: str,
    principal: Principal = Depends(current_principal),
    svc: ImportService = Depends(import_service),
) -> CommitResultResponse:
    """One bad row means nothing is written. Every write goes through `InventoryService`, so an
    imported row obeys the same merge and completion rules a typed one does."""
    try:
        result = svc.commit(principal.sub, job_id)
    except InventoryError as exc:
        raise _as_error(exc) from None
    return CommitResultResponse(
        added=result.added, updated=result.updated, skipped=result.skipped, rows=result.rows,
    )


@router.delete("/import/{job_id}", status_code=204, responses={404: {"model": ErrorResponse}})
def delete_import(
    job_id: str,
    principal: Principal = Depends(current_principal),
    svc: ImportService = Depends(import_service),
) -> None:
    try:
        svc.delete(principal.sub, job_id)
    except InventoryError as exc:
        raise _as_error(exc) from None


def _query_dict(raw: str | None) -> dict:
    """Parse a nested filter query string, e.g. `element=fire&condition=near_mint`.

    Passed as one parameter rather than spread across the signature so the export URL can be built
    by appending `/collection`'s own query string verbatim — one encoding, no translation step to
    get subtly wrong.
    """
    from urllib.parse import parse_qs

    if not raw:
        return {}
    return {key: values for key, values in parse_qs(raw).items()}
