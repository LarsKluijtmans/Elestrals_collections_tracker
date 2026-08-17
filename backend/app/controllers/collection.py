"""`/api/v1/collection` — the table, its filters, bulk actions, saved views and the dashboard.

Bolt 006. Everything here is user-scoped through the validated JWT `sub`, never a client-supplied
id, and a request for someone else's row returns **404, not 403** — the same rule bolt 004 set and
for the same reason: distinguishing "gone" from "not yours" hands a stranger an oracle over the
whole table.

Two things about this file are worth knowing before changing it.

**Filters are parsed once, into `FilterSet`, and never re-derived.** The query string, a saved
view's JSON and (in phase 2) a valuation slice all mean the same thing by "Fire holos in NM", and
story 033 is explicit that two implementations over one data model will disagree in a way that
reads to a collector as the valuation being broken.

**Paging is keyset, not offset.** A collector adds cards while scrolling, so an offset silently
repeats or skips rows. Neither surfaces as an error; both surface as "the table lost a card".
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..core.dependencies import (
    bulk_service,
    collection_browse_service,
    current_principal,
    dashboard_service,
    inventory_repository,
    saved_view_service,
    snapshot_service,
)
from ..models.base import utc_today
from ..models.inventory_item import InventoryItem
from ..repositories.inventory_repository import InventoryRepository
from ..schemas import (
    BulkEditRequest,
    BulkFailureModel,
    BulkResultResponse,
    CollectionPageResponse,
    CollectionRow,
    DashboardResponse,
    DashboardValueModel,
    ErrorResponse,
    MissingCardModel,
    MissingResponse,
    SavedViewModel,
    SavedViewPatch,
    SavedViewWrite,
    SelectionModel,
    SetCompletionModel,
    SnapshotHistoryResponse,
    SnapshotModel,
)
from ..security import Principal
from ..services.bulk_service import BulkService
from ..services.collection_browse_service import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    CollectionBrowseService,
)
from ..services.collection_filters import (
    DEFAULT_SORT,
    MULTI_VALUE,
    SORTS,
    TRISTATE,
    FilterSet,
    InvalidFilter,
)
from ..services.dashboard_service import DashboardService
from ..services.inventory_service import InventoryError, ItemFields
from ..services.saved_view_service import SavedViewService
from ..services.snapshot_service import SnapshotService

router = APIRouter(prefix="/api/v1", tags=["collection"])


def _err(status: int, code: str, message: str, **details) -> HTTPException:
    return HTTPException(status_code=status,
                         detail={"error": {"code": code, "message": message, "details": details}})


def _as_error(exc: InventoryError) -> HTTPException:
    return _err(exc.status, exc.code, str(exc) or exc.code)


def _filters_from_request(request: Request) -> FilterSet:
    """Read the filter vocabulary out of the query string.

    `getlist` per attribute, because `?element=fire&element=water` is how "or" is spelled in a URL
    and it is what makes a filtered view a shareable link. Unknown parameters are ignored rather
    than rejected — `?utm_source=...` on a shared link must not 400.
    """
    params: dict[str, object] = {}
    for name in MULTI_VALUE:
        values = request.query_params.getlist(name)
        if values:
            params[name] = values
    for name in TRISTATE:
        value = request.query_params.get(name)
        if value is not None:
            params[name] = value
    q = request.query_params.get("q")
    if q:
        params["q"] = q
    try:
        return FilterSet.from_params(params)
    except InvalidFilter as exc:
        raise _err(400, "bad_request", str(exc)) from None


def _row(item: InventoryItem) -> CollectionRow:
    """One table row, catalog fields included.

    Joined here rather than fetched per row by the client: a 50-row page that triggers 50 card
    lookups is a waterfall, and at the 10,000-row scale this bolt targets it is the difference
    between a table and a progress bar.
    """
    printing = item.printing
    card = printing.card if printing else None
    set_row = card.set if card else None
    return CollectionRow(
        id=item.id,
        printing_id=item.printing_id,
        card_id=card.id if card else "",
        name=card.name if card else "(unknown card)",
        set_code=set_row.code if set_row else "",
        collector_number=card.collector_number if card else "",
        element=card.element if card else None,
        rarity=printing.rarity if printing else "",
        finish=printing.finish if printing else "",
        language=printing.language if printing else "",
        edition=printing.edition if printing else "",
        image_url=printing.image_url if printing else None,
        alt_text=(
            f"{card.name} — {set_row.code if set_row else ''} {printing.rarity}".strip()
            if card and printing else ""
        ),
        condition=item.condition,
        quantity=item.quantity,
        is_graded=item.is_graded,
        grader=item.grader,
        grade=float(item.grade) if item.grade is not None else None,
        storage_location=item.storage_location,
        is_for_trade=item.is_for_trade,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


# --- the table -----------------------------------------------------------------------


@router.get(
    "/collection",
    response_model=CollectionPageResponse,
    summary="The collection table — filtered, sorted, keyset-paged",
    responses={400: {"model": ErrorResponse}},
)
def browse_collection(
    request: Request,
    sort: str = Query(default=DEFAULT_SORT),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = Query(default=None),
    principal: Principal = Depends(current_principal),
    svc: CollectionBrowseService = Depends(collection_browse_service),
) -> CollectionPageResponse:
    filters = _filters_from_request(request)
    if sort not in SORTS:
        raise _err(400, "bad_request", f"unknown sort {sort!r}", allowed=sorted(SORTS))

    try:
        page = svc.page(principal.sub, filters, sort=sort, limit=limit, cursor=cursor)
    except ValueError as exc:
        # A malformed or stale cursor. Loud, so the client restarts at page 1 rather than being
        # handed an arbitrary page and believing it is the next one.
        raise _err(400, "bad_request", str(exc) or "malformed cursor") from None

    return CollectionPageResponse(
        items=[_row(item) for item in page.items],
        total=page.total,
        next_cursor=page.next_cursor,
        filters=filters.to_json(),
        sort=sort,
    )


@router.get(
    "/collection/missing/{set_code}",
    response_model=MissingResponse,
    summary="Cards in a set with no owned printing",
    responses={404: {"model": ErrorResponse}},
)
def missing_from_set(
    set_code: str,
    principal: Principal = Depends(current_principal),
    svc: CollectionBrowseService = Depends(collection_browse_service),
) -> MissingResponse:
    """Story 024. **Missing is per card, not per printing** — owning the common version means the
    card is not missing, even without the holo. `card_count` is the set's *declared* printed size
    so this and the dashboard ring can never disagree."""
    report = svc.missing_from_set(principal.sub, set_code)
    if report is None:
        raise _err(404, "set_not_found", "No such set")
    return MissingResponse(
        set_code=report.set_code,
        set_name=report.set_name,
        card_count=report.card_count,
        owned_cards=report.owned_cards,
        # `asdict`, not `vars` — these are `slots=True` dataclasses and have no `__dict__` at all.
        missing=[MissingCardModel(**asdict(c)) for c in report.missing],
    )


# --- bulk actions --------------------------------------------------------------------


def _resolve(
    principal: Principal, body: SelectionModel, bulk: BulkService
) -> list[str]:
    filters = None
    if body.filters is not None:
        try:
            filters = FilterSet.from_params(body.filters)
        except InvalidFilter as exc:
            raise _err(400, "bad_request", str(exc)) from None
    if body.item_ids is None and filters is None:
        raise _err(400, "bad_request", "send item_ids or filters")
    try:
        return bulk.resolve(principal.sub, item_ids=body.item_ids, filters=filters)
    except InvalidFilter as exc:
        raise _err(400, "bad_request", str(exc)) from None
    except InventoryError as exc:
        raise _as_error(exc) from None


def _bulk_response(result) -> BulkResultResponse:
    return BulkResultResponse(
        requested=result.requested,
        applied=result.applied,
        failures=[BulkFailureModel(**asdict(f)) for f in result.failures],
        partial=result.partial,
    )


@router.post(
    "/collection/bulk/edit",
    response_model=BulkResultResponse,
    summary="Apply the same change to a selection",
    responses={400: {"model": ErrorResponse}},
)
def bulk_edit(
    body: BulkEditRequest,
    principal: Principal = Depends(current_principal),
    bulk: BulkService = Depends(bulk_service),
) -> BulkResultResponse:
    """Story 022. Returns **200 even when rows failed**, with the failures named.

    That is deliberate and it is the story's requirement: all-or-nothing over 500 rows fails the
    whole operation because one row moved in another tab, and a silent partial leaves a collector
    not knowing what happened. `partial` in the body is the flag the UI reads; the status code
    reports that the request was understood and acted on, which it was.
    """
    ids = _resolve(principal, body, bulk)
    fields = ItemFields(
        condition=body.condition,
        storage_location=body.storage_location,
        is_for_trade=body.is_for_trade,
    )
    return _bulk_response(bulk.edit(principal.sub, ids, fields))


@router.post(
    "/collection/bulk/delete",
    response_model=BulkResultResponse,
    summary="Delete a selection",
    responses={400: {"model": ErrorResponse}},
)
def bulk_delete(
    body: SelectionModel,
    principal: Principal = Depends(current_principal),
    bulk: BulkService = Depends(bulk_service),
) -> BulkResultResponse:
    ids = _resolve(principal, body, bulk)
    return _bulk_response(bulk.delete(principal.sub, ids))


@router.post(
    "/collection/selection/count",
    summary="How many rows a selection covers, before acting on it",
    responses={400: {"model": ErrorResponse}},
)
def selection_count(
    body: SelectionModel,
    principal: Principal = Depends(current_principal),
    items: InventoryRepository = Depends(inventory_repository),
) -> dict:
    """What "select all" needs before it can say a number.

    Story 022 requires the confirmation to *name the count*, and a bulk delete confirmation that
    says "delete these?" without saying how many is the one that gets clicked through.
    """
    if body.item_ids is not None:
        return {"count": len(set(body.item_ids))}
    try:
        filters = FilterSet.from_params(body.filters or {})
    except InvalidFilter as exc:
        raise _err(400, "bad_request", str(exc)) from None
    return {"count": items.count_matching(principal.sub, filters)}


# --- saved views ---------------------------------------------------------------------


def _view_model(view) -> SavedViewModel:
    return SavedViewModel(
        id=view.id, name=view.name, filters=view.filters, sort=view.sort,
        density=view.density, created_at=view.created_at, updated_at=view.updated_at,
    )


@router.get("/collection/views", response_model=list[SavedViewModel])
def list_views(
    principal: Principal = Depends(current_principal),
    svc: SavedViewService = Depends(saved_view_service),
) -> list[SavedViewModel]:
    return [_view_model(v) for v in svc.list_for_user(principal.sub)]


@router.post(
    "/collection/views",
    response_model=SavedViewModel,
    status_code=201,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def create_view(
    body: SavedViewWrite,
    principal: Principal = Depends(current_principal),
    svc: SavedViewService = Depends(saved_view_service),
) -> SavedViewModel:
    try:
        filters = FilterSet.from_params(body.filters)
        view = svc.create(
            principal.sub, name=body.name, filters=filters,
            sort=body.sort, density=body.density,
        )
    except InvalidFilter as exc:
        raise _err(400, "bad_request", str(exc)) from None
    except InventoryError as exc:
        raise _as_error(exc) from None
    return _view_model(view)


@router.patch(
    "/collection/views/{view_id}",
    response_model=SavedViewModel,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
               409: {"model": ErrorResponse}},
)
def patch_view(
    view_id: str,
    body: SavedViewPatch,
    principal: Principal = Depends(current_principal),
    svc: SavedViewService = Depends(saved_view_service),
) -> SavedViewModel:
    try:
        filters = FilterSet.from_params(body.filters) if body.filters is not None else None
        view = svc.update(
            principal.sub, view_id, name=body.name, filters=filters,
            sort=body.sort, density=body.density,
        )
    except InvalidFilter as exc:
        raise _err(400, "bad_request", str(exc)) from None
    except InventoryError as exc:
        raise _as_error(exc) from None
    return _view_model(view)


@router.delete(
    "/collection/views/{view_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
)
def delete_view(
    view_id: str,
    principal: Principal = Depends(current_principal),
    svc: SavedViewService = Depends(saved_view_service),
) -> None:
    try:
        svc.delete(principal.sub, view_id)
    except InventoryError as exc:
        raise _as_error(exc) from None


# --- dashboard -----------------------------------------------------------------------


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    principal: Principal = Depends(current_principal),
    svc: DashboardService = Depends(dashboard_service),
) -> DashboardResponse:
    """Story 036. Note what is *not* here: a zero value tile.

    When nothing is priced, `value` is `null` and the tile says "available in phase 2" in words.
    A zero would be a claim about what the collection is worth, and it would be false.
    """
    data = svc.build(principal.sub)
    return DashboardResponse(
        total_items=data.total_items,
        distinct_printings=data.distinct_printings,
        sets_started=data.sets_started,
        value=DashboardValueModel(**asdict(data.value)) if data.value else None,
        rings=[
            SetCompletionModel(
                set_code=r.set_code, set_name=r.set_name, owned_cards=r.owned_cards,
                card_count=r.card_count, total_quantity=r.total_quantity, ratio=r.ratio,
            )
            for r in data.rings
        ],
        recent=[_row(item) for item in data.recent],
        is_empty=data.is_empty,
    )


@router.get("/collection/history", response_model=SnapshotHistoryResponse)
def snapshot_history(
    days: int = Query(default=365, ge=1, le=1095),
    principal: Principal = Depends(current_principal),
    svc: SnapshotService = Depends(snapshot_service),
) -> SnapshotHistoryResponse:
    """The user's own `collection_snapshots` series.

    Phase 1 reads it for the count-over-time chart; phase 2's portfolio page reads the same rows
    once its nightly valuation has filled in `total_value_cents`. Rows before that carry `null`
    value and `none` confidence, which the chart draws as a gap rather than as zero.
    """
    from datetime import timedelta

    # UTC, because `taken_on` was written in UTC. See `utc_today`.
    since = utc_today() - timedelta(days=days - 1)
    rows = svc.history(principal.sub, since=since)
    return SnapshotHistoryResponse(items=[
        SnapshotModel(
            taken_on=r.taken_on, item_count=r.item_count,
            distinct_printings=r.distinct_printings,
            total_value_cents=r.total_value_cents, currency=r.currency,
            valuation_confidence=r.valuation_confidence,
        )
        for r in rows
    ])
