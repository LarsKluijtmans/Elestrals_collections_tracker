"""`/api/v1/sealed` and `/api/v1/wishlist` — bolt 007.

Two thin surfaces over patterns bolt 004 established, and they inherit its rules unchanged: every
route is user-scoped through the validated JWT `sub`, and someone else's row is **404, never 403**.
There is an explicit cross-user test per endpoint, as bolt 004 requires and this bolt reuses.

The one thing worth pointing at: `POST /sealed/{id}/open` flips a flag and **creates no singles**.
See `SealedService.open` for why that is a permanent refusal rather than a missing feature.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..core.dependencies import current_principal, sealed_service, wishlist_service
from ..models.sealed_inventory_item import SealedInventoryItem
from ..models.wishlist_item import WishlistItem
from ..schemas import (
    AddSealedRequest,
    AddWishRequest,
    ErrorResponse,
    PatchSealedRequest,
    PatchWishRequest,
    SealedItemResponse,
    SealedListResponse,
    WishlistItemResponse,
    WishlistResponse,
)
from ..security import Principal
from ..services.inventory_service import InventoryError
from ..services.sealed_service import SealedFields, SealedService
from ..services.wishlist_service import WishFields, WishlistService

router = APIRouter(prefix="/api/v1", tags=["sealed", "wishlist"])


def _as_error(exc: InventoryError) -> HTTPException:
    return HTTPException(
        status_code=exc.status,
        detail={"error": {"code": exc.code, "message": str(exc) or exc.code, "details": {}}},
    )


def _sealed_view(item: SealedInventoryItem) -> SealedItemResponse:
    product = item.product
    return SealedItemResponse(
        id=item.id,
        sealed_product_id=item.sealed_product_id,
        name=product.name if product else "(unknown product)",
        kind=product.kind if product else "other",
        image_url=product.image_url if product else None,
        quantity=item.quantity,
        is_sealed=item.is_sealed,
        acquired_on=item.acquired_on,
        acquired_unit_price_cents=item.acquired_unit_price_cents,
        acquired_currency=item.acquired_currency,
        storage_location=item.storage_location,
        notes=item.notes,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _wish_view(item: WishlistItem, *, owned: bool = False) -> WishlistItemResponse:
    printing = item.printing
    card = printing.card if printing else None
    return WishlistItemResponse(
        id=item.id,
        printing_id=item.printing_id,
        card_id=card.id if card else "",
        name=card.name if card else "(unknown card)",
        set_code=card.set.code if card and card.set else "",
        collector_number=card.collector_number if card else "",
        element=card.element if card else None,
        rarity=printing.rarity if printing else "",
        finish=printing.finish if printing else "",
        desired_quantity=item.desired_quantity,
        priority=item.priority,
        max_price_cents=item.max_price_cents,
        max_price_currency=item.max_price_currency,
        notes=item.notes,
        #: True when this printing is now in the collection. The UI prompts from this; nothing
        #: clears the wish on its own.
        owned=owned,
        created_at=item.created_at,
    )


# --- sealed --------------------------------------------------------------------------


@router.get("/sealed", response_model=SealedListResponse)
def list_sealed(
    principal: Principal = Depends(current_principal),
    svc: SealedService = Depends(sealed_service),
) -> SealedListResponse:
    """Sealed holdings, and **only** sealed holdings.

    These never appear in `/collection` and never move a completion figure — guaranteed by living
    in a different table rather than by every query remembering to filter them out.
    """
    items = svc.list_for_user(principal.sub)
    return SealedListResponse(
        items=[_sealed_view(i) for i in items],
        total=len(items),
        sealed_count=sum(i.quantity for i in items if i.is_sealed),
        opened_count=sum(i.quantity for i in items if not i.is_sealed),
    )


@router.post(
    "/sealed", response_model=SealedItemResponse, status_code=201,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def add_sealed(
    body: AddSealedRequest,
    principal: Principal = Depends(current_principal),
    svc: SealedService = Depends(sealed_service),
) -> SealedItemResponse:
    try:
        result = svc.add(
            principal.sub,
            sealed_product_id=body.sealed_product_id,
            quantity=body.quantity,
            is_sealed=body.is_sealed,
            fields=SealedFields(
                acquired_on=body.acquired_on,
                acquired_unit_price_cents=body.acquired_unit_price_cents,
                acquired_currency=body.acquired_currency,
                storage_location=body.storage_location,
                notes=body.notes,
            ),
        )
    except InventoryError as exc:
        raise _as_error(exc) from None
    return _sealed_view(result.item)


@router.post(
    "/sealed/{item_id}/open", response_model=SealedItemResponse,
    summary="Mark copies opened — creates no singles",
    responses={404: {"model": ErrorResponse}},
)
def open_sealed(
    item_id: str,
    quantity: int = 1,
    principal: Principal = Depends(current_principal),
    svc: SealedService = Depends(sealed_service),
) -> SealedItemResponse:
    """**No singles are created here, and none ever will be.**

    A box has an expected distribution and an actual pull, and they are never the same. Generated
    cards would be wrong every single time, and wrong in a way the collector has to find and undo
    one row at a time — having first noticed their collection contains cards they do not own.
    """
    try:
        return _sealed_view(svc.open(principal.sub, item_id, quantity=quantity))
    except InventoryError as exc:
        raise _as_error(exc) from None


@router.patch(
    "/sealed/{item_id}", response_model=SealedItemResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def patch_sealed(
    item_id: str,
    body: PatchSealedRequest,
    principal: Principal = Depends(current_principal),
    svc: SealedService = Depends(sealed_service),
) -> SealedItemResponse:
    try:
        return _sealed_view(
            svc.edit(principal.sub, item_id, SealedFields(**body.model_dump(exclude_unset=True)))
        )
    except InventoryError as exc:
        raise _as_error(exc) from None


@router.delete("/sealed/{item_id}", status_code=204, responses={404: {"model": ErrorResponse}})
def delete_sealed(
    item_id: str,
    principal: Principal = Depends(current_principal),
    svc: SealedService = Depends(sealed_service),
) -> None:
    try:
        svc.remove(principal.sub, item_id)
    except InventoryError as exc:
        raise _as_error(exc) from None


# --- wishlist ------------------------------------------------------------------------


@router.get("/wishlist", response_model=WishlistResponse)
def list_wishlist(
    principal: Principal = Depends(current_principal),
    svc: WishlistService = Depends(wishlist_service),
) -> WishlistResponse:
    items = svc.list_for_user(principal.sub)
    owned_ids = {i.id for i in svc.acquired_but_still_wished(principal.sub)}
    return WishlistResponse(
        items=[_wish_view(i, owned=i.id in owned_ids) for i in items],
        total=len(items),
        #: How many wishes are for printings now owned. The prompt's trigger — and nothing more:
        #: a wish clears only when the collector says so.
        acquired_count=len(owned_ids),
    )


@router.post(
    "/wishlist", response_model=WishlistItemResponse, status_code=201,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def add_wish(
    body: AddWishRequest,
    principal: Principal = Depends(current_principal),
    svc: WishlistService = Depends(wishlist_service),
) -> WishlistItemResponse:
    try:
        item = svc.add(
            principal.sub,
            printing_id=body.printing_id,
            desired_quantity=body.desired_quantity,
            priority=body.priority,
            max_price_cents=body.max_price_cents,
            max_price_currency=body.max_price_currency,
            notes=body.notes,
        )
    except InventoryError as exc:
        raise _as_error(exc) from None
    return _wish_view(item)


@router.patch(
    "/wishlist/{item_id}", response_model=WishlistItemResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def patch_wish(
    item_id: str,
    body: PatchWishRequest,
    principal: Principal = Depends(current_principal),
    svc: WishlistService = Depends(wishlist_service),
) -> WishlistItemResponse:
    try:
        return _wish_view(
            svc.edit(principal.sub, item_id, WishFields(**body.model_dump(exclude_unset=True)))
        )
    except InventoryError as exc:
        raise _as_error(exc) from None


@router.delete("/wishlist/{item_id}", status_code=204, responses={404: {"model": ErrorResponse}})
def delete_wish(
    item_id: str,
    principal: Principal = Depends(current_principal),
    svc: WishlistService = Depends(wishlist_service),
) -> None:
    """The **only** way a wish is removed.

    Acquiring the printing does not do it. A collector may want a second copy or a better
    condition, and deleting their stated intent because a row appeared elsewhere loses information
    they never agreed to lose.
    """
    try:
        svc.remove(principal.sub, item_id)
    except InventoryError as exc:
        raise _as_error(exc) from None
