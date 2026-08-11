"""Inventory writes and the completion projection — stories 013, 014, 015, 023.

Every route is user-scoped through the validated JWT `sub`, never a client-supplied id. A
request for someone else's item returns **404, not 403**: distinguishing "gone" from "not
yours" hands a stranger an oracle over the whole table, and there is an explicit cross-user
test for each of these endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.dependencies import completion_service, current_principal, inventory_service
from ..core.pagination import decode_offset, next_offset_cursor
from ..models.inventory_item import InventoryItem
from ..schemas import (
    AddInventoryRequest,
    AddInventoryResponse,
    CompletionResponse,
    ErrorResponse,
    InventoryItemResponse,
    PagedInventory,
    PatchInventoryRequest,
    SetCompletionModel,
)
from ..security import Principal
from ..services.completion_service import CompletionService
from ..services.inventory_service import InventoryError, InventoryService, ItemFields

router = APIRouter(prefix="/api/v1", tags=["inventory"])


def _err(status: int, code: str, message: str, **details) -> HTTPException:
    return HTTPException(status_code=status,
                         detail={"error": {"code": code, "message": message, "details": details}})


def _as_error(exc: InventoryError) -> HTTPException:
    return _err(exc.status, exc.code, str(exc) or exc.code)


def _view(item: InventoryItem) -> InventoryItemResponse:
    return InventoryItemResponse(
        id=item.id,
        printing_id=item.printing_id,
        condition=item.condition,
        quantity=item.quantity,
        is_graded=item.is_graded,
        grader=item.grader,
        grade=float(item.grade) if item.grade is not None else None,
        acquired_on=item.acquired_on,
        acquired_unit_price_cents=item.acquired_unit_price_cents,
        acquired_currency=item.acquired_currency,
        storage_location=item.storage_location,
        notes=item.notes,
        is_for_trade=item.is_for_trade,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post(
    "/inventory",
    response_model=AddInventoryResponse,
    status_code=201,
    summary="Add copies of a printing, merging with an existing ungraded row",
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
def add_item(
    body: AddInventoryRequest,
    principal: Principal = Depends(current_principal),
    svc: InventoryService = Depends(inventory_service),
) -> AddInventoryResponse:
    try:
        result = svc.add(
            principal.sub,
            printing_id=body.printing_id,
            condition=body.condition,
            quantity=body.quantity,
            is_graded=body.is_graded,
            grader=body.grader,
            grade=body.grade,
            acquired_on=body.acquired_on,
            acquired_unit_price_cents=body.acquired_unit_price_cents,
            acquired_currency=body.acquired_currency,
            storage_location=body.storage_location,
            notes=body.notes,
            is_for_trade=body.is_for_trade,
        )
    except InventoryError as exc:
        raise _as_error(exc) from None
    return AddInventoryResponse(item=_view(result.item), merged=result.merged)


@router.get(
    "/inventory",
    response_model=PagedInventory,
    summary="The caller's inventory (the full filtered table is bolt 006)",
)
def list_items(
    limit: int = Query(default=100, ge=1, le=250),
    cursor: str | None = Query(default=None),
    printing_id: str | None = Query(default=None),
    principal: Principal = Depends(current_principal),
    svc: InventoryService = Depends(inventory_service),
) -> PagedInventory:
    try:
        offset = decode_offset(cursor)
    except ValueError:
        raise _err(400, "bad_request", "Malformed cursor") from None

    items, total = svc.list_items(
        principal.sub, limit=limit, offset=offset, printing_id=printing_id
    )
    return PagedInventory(
        items=[_view(i) for i in items],
        next_cursor=next_offset_cursor(
            offset=offset, page_size=limit, has_more=offset + len(items) < total
        ),
        total=total,
    )


@router.patch(
    "/inventory/{item_id}",
    response_model=InventoryItemResponse,
    summary="Edit an item; a condition change may merge it into an existing row",
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
def patch_item(
    item_id: str,
    body: PatchInventoryRequest,
    principal: Principal = Depends(current_principal),
    svc: InventoryService = Depends(inventory_service),
) -> InventoryItemResponse:
    try:
        item = svc.edit(principal.sub, item_id, ItemFields(**body.model_dump(exclude_unset=True)))
    except InventoryError as exc:
        raise _as_error(exc) from None
    return _view(item)


@router.delete(
    "/inventory/{item_id}",
    status_code=204,
    summary="Remove an item",
    responses={404: {"model": ErrorResponse}},
)
def delete_item(
    item_id: str,
    principal: Principal = Depends(current_principal),
    svc: InventoryService = Depends(inventory_service),
) -> None:
    try:
        svc.remove(principal.sub, item_id)
    except InventoryError as exc:
        raise _as_error(exc) from None


@router.get(
    "/completion",
    response_model=CompletionResponse,
    summary="Per-set completion for the caller",
)
def get_completion(
    principal: Principal = Depends(current_principal),
    svc: CompletionService = Depends(completion_service),
    inv: InventoryService = Depends(inventory_service),
) -> CompletionResponse:
    """Deliberately its own endpoint rather than a field on `/sets`.

    `/sets` is public and cached; completion is per-user. Merging them would put one
    collector's data behind a shared cache key.
    """
    views = svc.view(principal.sub)
    return CompletionResponse(
        sets=[
            SetCompletionModel(
                set_code=v.set_code, set_name=v.set_name, owned_cards=v.owned_cards,
                card_count=v.card_count, total_quantity=v.total_quantity, ratio=v.ratio,
            )
            for v in views
        ],
        total_items=inv.count(principal.sub),
        total_quantity=inv.total_quantity(principal.sub),
    )
