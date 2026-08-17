"""The dashboard — story 036.

Four tiles, three completion rings, ten recent changes, and one deliberate refusal.

**The value tile does not render a zero.** Until intent 002's rollups are publishing, this returns
`None` for value and the tile reads "available in phase 2". A zero is a claim — "your collection is
worth nothing" — and it is false. The story is explicit about it, and the same reasoning runs
through `collection_snapshots.total_value_cents` being nullable and through the price tab's empty
state: *not measured* and *measured as zero* are different facts and must look different.

**The empty state is the more important of the two designs.** It is what every new user sees first,
so `is_empty` is part of the payload rather than something the client infers from four zeroes —
inferring it is how "0 items, 0 printings, 0 sets" ends up rendered to somebody who signed up
ninety seconds ago.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..models.inventory_item import InventoryItem
from ..repositories.inventory_repository import InventoryRepository
from ..repositories.price_repository import PriceRepository
from .completion_service import CompletionService, CompletionView
from .valuation_service import ValuationService

#: Story 036 asks for "the three closest to completion". Closest, not largest — a set you are two
#: cards from finishing is the actionable one.
RINGS = 3
RECENT = 10


@dataclass(frozen=True, slots=True)
class DashboardValue:
    total_cents: int
    currency: str
    confidence: str
    #: How many of the holdings carried a price. Shown beside the figure, never hidden — a total
    #: over 40% of a collection is a different number from a total over all of it.
    valued_items: int
    total_items: int


@dataclass(frozen=True, slots=True)
class Dashboard:
    total_items: int
    distinct_printings: int
    sets_started: int
    #: `None` means "not available", which the tile says in words. It never becomes 0.
    value: DashboardValue | None
    rings: list[CompletionView]
    recent: list[InventoryItem]
    is_empty: bool


class DashboardService:
    def __init__(
        self,
        items: InventoryRepository,
        completion: CompletionService,
        prices: PriceRepository | None = None,
    ) -> None:
        self._items = items
        self._completion = completion
        self._prices = prices

    def build(self, user_sub: str, *, currency: str = "EUR") -> Dashboard:
        total_items = self._items.total_quantity(user_sub)
        distinct = self._items.distinct_printings(user_sub)

        views = [v for v in self._completion.view(user_sub) if v.owned_cards > 0]
        # Closest to completion first, and a set already at 100% is not "closest to completion",
        # it is finished — so completed sets fall to the back rather than permanently occupying
        # all three rings.
        rings = sorted(
            views,
            key=lambda v: (v.ratio >= 1.0, -v.ratio, v.set_code),
        )[:RINGS]

        return Dashboard(
            total_items=total_items,
            distinct_printings=distinct,
            sets_started=len(views),
            value=self._value(user_sub, currency=currency),
            rings=rings,
            recent=self._items.recent_activity(user_sub, limit=RECENT),
            is_empty=total_items == 0,
        )

    def _value(self, user_sub: str, *, currency: str) -> DashboardValue | None:
        """Phase 2's number, or nothing at all.

        Returns `None` both when pricing is not wired up and when it is wired up but has priced
        nothing — a collection where zero holdings have a price has no total, and rendering
        "€0.00 (0 of 400 valued)" is a worse answer than "not available yet".
        """
        if self._prices is None:
            return None

        valuation = ValuationService(self._prices).value(
            self._items.all_for_user(user_sub), currency=currency
        )
        if not valuation.valued_items:
            return None

        return DashboardValue(
            total_cents=valuation.total_cents,
            currency=currency,
            confidence=valuation.confidence,
            valued_items=valuation.valued_items,
            total_items=valuation.total_items,
        )
