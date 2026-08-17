"""`/api/v1/prices` and `/api/v1/portfolio` — what a collector sees.

Rollups only. No raw listing, no match note, no rejection reason reaches a non-admin — not as a
policy about secrecy, but because that material is uneven scraped data and presenting it to a
collector as a product would misrepresent what it is.

Two rules run through every response here and are worth stating once:

* **No monetary figure without its confidence and its observation count.** A median from two
  sales and a median from two hundred are the same number and mean very different things.
* **An empty state is an empty state.** A printing with no data returns `null` and a count of
  zero, never a zero price — a chart drawn at zero reads as "this card is worthless", which is a
  different and false claim from "we have not seen one sell".
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel

from ..config import settings
from ..core.dependencies import (
    current_principal, inventory_repository, price_repository, valuation_service,
)
from ..repositories.inventory_repository import InventoryRepository
from ..repositories.price_repository import PriceRepository
from ..security import Principal
from ..services.valuation_service import ValuationService

router = APIRouter(prefix="/api/v1", tags=["prices"])

#: 30 / 90 / 365 / all, as the price tab offers them.
_RANGES = {"30d": 30, "90d": 90, "365d": 365, "all": None}


class PricePoint(BaseModel):
    day: date
    low_cents: int
    median_cents: int
    high_cents: int
    currency: str
    #: Both required on every point. See the module docstring.
    observation_count: int
    confidence: str


class PriceHistory(BaseModel):
    printing_id: str
    sale_type: str
    condition: str | None
    points: list[PricePoint]
    #: Present and empty rather than absent, so the client renders "no observations yet" instead
    #: of a flat line at zero.
    is_empty: bool
    #: When the harvester last published. A stale rollup says so rather than looking current.
    priced_as_of: str | None
    is_stale: bool


class Mover(BaseModel):
    printing_id: str
    from_cents: int
    to_cents: int
    change_pct: float


class MarketOverview(BaseModel):
    movers_up: list[Mover]
    movers_down: list[Mover]
    window_days: int
    min_observations: int
    priced_as_of: str | None


class PortfolioResponse(BaseModel):
    total_cents: int
    currency: str
    valued_items: int
    unvalued_items: int
    unvalued_reasons: dict[str, int]
    coverage: float
    confidence: str
    priced_as_of: str | None
    unvalued_item_ids: list[str]


@router.get("/prices/printings/{printing_id}", response_model=PriceHistory)
def price_history(
    printing_id: str,
    response: Response,
    range_key: str = Query(default="90d", alias="range", pattern="^(30d|90d|365d|all)$"),
    sale_type: str = Query(default="sold", pattern="^(sold|listed)$"),
    condition: str | None = Query(default=None),
    prices: PriceRepository = Depends(price_repository),
) -> PriceHistory:
    """The card price tab. Public, like the phase-1 catalog pages, and cacheable for the same
    reason: it does not vary by caller."""
    days = _RANGES[range_key]
    since = date.today() - timedelta(days=days) if days else None
    rows = prices.history_for_printing(
        printing_id, since=since, sale_type=sale_type, condition=condition
    )
    computed = prices.last_computed_at()
    response.headers["Cache-Control"] = f"public, max-age={settings.catalog_cache_seconds}"

    return PriceHistory(
        printing_id=printing_id,
        sale_type=sale_type,
        condition=condition,
        points=[
            PricePoint(
                day=row.day, low_cents=row.low_cents, median_cents=row.median_cents,
                high_cents=row.high_cents, currency=row.currency,
                observation_count=row.observation_count, confidence=row.confidence,
            )
            for row in rows
        ],
        is_empty=not rows,
        priced_as_of=computed.isoformat() if computed else None,
        is_stale=_is_stale(computed),
    )


@router.get("/prices/overview", response_model=MarketOverview)
def market_overview(
    response: Response,
    window_days: int = Query(default=7, ge=1, le=90),
    prices: PriceRepository = Depends(price_repository),
) -> MarketOverview:
    """Top movers. Public.

    `min_observations` is the difference between a market overview and a noise generator: without
    it the list is dominated by printings with one sale each, which is the data least worth
    ranking. It is returned in the response so the number is documented where it is used.
    """
    min_observations = 3
    rows = prices.movers(window_days=window_days, min_observations=min_observations, limit=20)
    computed = prices.last_computed_at()
    response.headers["Cache-Control"] = f"public, max-age={settings.catalog_cache_seconds}"

    movers = [
        Mover(printing_id=pid, from_cents=was, to_cents=now, change_pct=round(pct, 2))
        for pid, was, now, pct in rows
    ]
    return MarketOverview(
        movers_up=sorted([m for m in movers if m.change_pct > 0],
                         key=lambda m: m.change_pct, reverse=True)[:10],
        movers_down=sorted([m for m in movers if m.change_pct < 0],
                           key=lambda m: m.change_pct)[:10],
        window_days=window_days,
        min_observations=min_observations,
        priced_as_of=computed.isoformat() if computed else None,
    )


@router.get("/portfolio", response_model=PortfolioResponse)
def portfolio(
    currency: str = Query(default="EUR", min_length=3, max_length=3),
    principal: Principal = Depends(current_principal),
    items: InventoryRepository = Depends(inventory_repository),
    valuation: ValuationService = Depends(valuation_service),
) -> PortfolioResponse:
    """What this collection is worth, and how much of it that covers.

    `user_sub` comes from the validated token and nowhere else — the phase-1 rule that ownership
    is a signature rather than a filter applies here exactly as it does to inventory.
    """
    holdings = items.all_for_user(principal.sub)
    result = valuation.value(holdings, currency=currency)
    payload = result.as_dict()
    # Serialised here rather than left as a datetime: the field is a string in the contract, so
    # the whole surface reports "when was this priced" in one format.
    priced_as_of = payload.pop("priced_as_of")
    return PortfolioResponse(
        **payload,
        priced_as_of=priced_as_of.isoformat() if priced_as_of else None,
        # A count is informative; being able to see *which* ones is actionable, and it is usually
        # the same lead the admin console works from.
        unvalued_item_ids=result.unvalued_item_ids,
    )


def _is_stale(computed: datetime | None) -> bool:
    """`harvest-api` being down degrades freshness, never availability (FR-13) — so a stale
    rollup is labelled rather than withheld.

    `computed_at` comes back **naive** from both MySQL and SQLite, whatever `DateTime(timezone=
    True)` suggests; neither driver attaches a tzinfo on read. Comparing that to an aware `now()`
    raises, so it is normalised here. Everything this project stores is UTC — standards §4 — so
    stamping UTC on a naive value is a correction, not an assumption.
    """
    if computed is None:
        return True
    if computed.tzinfo is None:
        computed = computed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - computed) > timedelta(
        hours=settings.price_stale_after_hours
    )
