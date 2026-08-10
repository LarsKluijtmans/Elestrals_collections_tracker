"""The public catalog surface — stories 010, 011, 012.

Every route here is **anonymous**. None of them takes a `Principal`, reads a user table, or
depends on anything that does. That is not an oversight: `api-conventions.md` requires public
reads never to vary on the caller, and these responses are cached for minutes at a time with no
`Vary: Authorization`. A user-specific field added here would silently serve one collector's
data to another.

Set completion is per-user and therefore lives on bolt 004's `/api/v1/completion`, merged into
the gallery client-side.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from ..config import settings
from ..core.dependencies import card_detail_service, card_search_service, set_browse_service
from ..core.pagination import decode_offset, next_offset_cursor
from ..repositories.card_repository import MIN_TERM_LENGTH, SearchQuery
from ..schemas import (
    CardDetailResponse,
    ErrorResponse,
    PagedCardSearch,
    SetChecklistResponse,
    SetListResponse,
)
from ..services.catalog_read_service import CardDetailService, CardSearchService, SetBrowseService

router = APIRouter(prefix="/api/v1", tags=["catalog"])

_CACHE = (
    f"public, max-age={settings.catalog_cache_seconds}, "
    f"stale-while-revalidate={settings.catalog_cache_seconds * 12}"
)


def _err(status: int, code: str, message: str, **details) -> HTTPException:
    return HTTPException(status_code=status,
                         detail={"error": {"code": code, "message": message, "details": details}})


def _cacheable(response: Response) -> None:
    response.headers["Cache-Control"] = _CACHE


def _offset(cursor: str | None) -> int:
    try:
        return decode_offset(cursor)
    except ValueError:
        raise _err(400, "bad_request", "Malformed cursor") from None


@router.get("/cards", response_model=PagedCardSearch, summary="Search the card catalog")
def search_cards(
    response: Response,
    q: str = Query(default="", max_length=128),
    set_code: list[str] = Query(default_factory=list),
    element: list[str] = Query(default_factory=list),
    card_type: list[str] = Query(default_factory=list),
    rarity: list[str] = Query(default_factory=list),
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
    svc: CardSearchService = Depends(card_search_service),
) -> PagedCardSearch:
    """Repeated params OR within an attribute, distinct params AND across — the filter algebra
    the URL-serialised UI filters use, so the two cannot drift.

    A term under two characters returns an empty page as a **200**, without querying. Someone
    mid-keystroke has not made a mistake, and a one-character prefix matches a third of the
    catalog.
    """
    _cacheable(response)
    offset = _offset(cursor)

    if len(q.strip()) < MIN_TERM_LENGTH:
        return PagedCardSearch(items=[], next_cursor=None, total=0)

    items, total = svc.search(SearchQuery(
        term=q, set_codes=set_code, elements=element, card_types=card_type,
        rarities=rarity, limit=limit, offset=offset,
    ))
    return PagedCardSearch(
        items=items,
        next_cursor=next_offset_cursor(
            offset=offset, page_size=limit, has_more=offset + len(items) < total
        ),
        total=total,
    )


@router.get(
    "/cards/{card_id}",
    response_model=CardDetailResponse,
    summary="One card with every printing",
    responses={404: {"model": ErrorResponse}},
)
def get_card(
    card_id: str,
    response: Response,
    svc: CardDetailService = Depends(card_detail_service),
) -> CardDetailResponse:
    _cacheable(response)
    detail = svc.detail(card_id)
    if detail is None:
        raise _err(404, "card_not_found", "Card not found", card_id=card_id)
    return detail


@router.get("/sets", response_model=SetListResponse, summary="Set gallery")
def list_sets(
    response: Response,
    series: str | None = Query(default=None, max_length=64),
    svc: SetBrowseService = Depends(set_browse_service),
) -> SetListResponse:
    _cacheable(response)
    return SetListResponse(items=svc.list_sets(series=series))


@router.get(
    "/sets/{code}",
    response_model=SetChecklistResponse,
    summary="Set checklist",
    responses={404: {"model": ErrorResponse}},
)
def get_set(
    code: str,
    response: Response,
    limit: int = Query(default=100, ge=1, le=250),
    cursor: str | None = Query(default=None),
    svc: SetBrowseService = Depends(set_browse_service),
) -> SetChecklistResponse:
    _cacheable(response)
    offset = _offset(cursor)

    result = svc.checklist(code, limit=limit, offset=offset)
    if result is None:
        raise _err(404, "set_not_found", "Set not found", set_code=code)

    summary, items, total = result
    return SetChecklistResponse(
        set=summary,
        items=items,
        next_cursor=next_offset_cursor(
            offset=offset, page_size=limit, has_more=offset + len(items) < total
        ),
        total=total,
    )
