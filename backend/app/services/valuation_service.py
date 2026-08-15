"""What a collection is worth, and how much of it that number actually covers.

The rule the whole service is arranged around: **an item with no price is excluded and counted,
never treated as zero.** A zero for an unpriced holding produces a total that is confidently
wrong and silently low; a stated coverage produces a total that is honestly partial. The second
is usable and the first is not, and the difference is invisible to the person reading it unless
we say so.

Three exclusions, each for a reason that is recorded somewhere upstream:

    no data        nothing has been seen selling. The commonest case, and the one the
                   `unvalued` count exists for
    graded         the matcher refuses graded slabs on purpose (a PSA 10 and a raw copy are two
                   markets), so no graded price exists to value them with
    no rate        a currency we have no FX rate for that day. Excluded rather than converted
                   at a stale rate

Valuation reads **`sold` only**. An asking price is not evidence that anyone paid it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..models.inventory_item import InventoryItem
from ..repositories.price_repository import PriceRepository

#: Ordered worst-first, so the overall confidence of a set of items is `min()`.
_CONFIDENCE_ORDER = ("low", "medium", "high")


@dataclass
class ValuedItem:
    item_id: str
    printing_id: str
    quantity: int
    unit_cents: int
    currency: str
    confidence: str
    observation_count: int

    @property
    def total_cents(self) -> int:
        return self.unit_cents * self.quantity


@dataclass
class Valuation:
    total_cents: int = 0
    currency: str = "EUR"
    valued_items: int = 0
    #: Counted, listed, and never folded into the total as zero.
    unvalued_items: int = 0
    unvalued_reasons: dict[str, int] = field(default_factory=dict)
    unvalued_item_ids: list[str] = field(default_factory=list)
    confidence: str = "low"
    priced_as_of: datetime | None = None
    items: list[ValuedItem] = field(default_factory=list)

    @property
    def total_items(self) -> int:
        return self.valued_items + self.unvalued_items

    @property
    def coverage(self) -> float:
        return (self.valued_items / self.total_items) if self.total_items else 0.0

    def as_dict(self) -> dict:
        return {
            "total_cents": self.total_cents,
            "currency": self.currency,
            "valued_items": self.valued_items,
            "unvalued_items": self.unvalued_items,
            "unvalued_reasons": self.unvalued_reasons,
            "coverage": round(self.coverage, 4),
            "confidence": self.confidence,
            "priced_as_of": self.priced_as_of,
        }


class ValuationService:
    def __init__(self, prices: PriceRepository) -> None:
        self._prices = prices

    def value(self, items: list[InventoryItem], *, currency: str = "EUR") -> Valuation:
        """Sum `quantity × median for that printing and condition`.

        Runs in this service rather than in the harvester because it joins the user's inventory,
        which `harvest-api` cannot read and should not be able to.
        """
        result = Valuation(currency=currency)
        if not items:
            return result

        printing_ids = sorted({item.printing_id for item in items})
        rollups = self._prices.latest_for_printings(
            printing_ids, sale_type="sold", currency=currency
        )
        result.priced_as_of = self._prices.last_computed_at()

        confidences: list[str] = []
        for item in items:
            reason = self._unvaluable(item)
            if reason:
                self._exclude(result, item, reason)
                continue

            # The exact condition first; then the unstated bucket. Never a *different* condition:
            # a Heavily Played copy priced at Near Mint is a wrong number with a plausible face.
            rollup = (
                rollups.get((item.printing_id, item.condition or ""))
                or rollups.get((item.printing_id, ""))
            )
            if rollup is None:
                self._exclude(result, item, "no_data")
                continue

            valued = ValuedItem(
                item_id=item.id,
                printing_id=item.printing_id,
                quantity=item.quantity,
                unit_cents=rollup.median_cents,
                currency=rollup.currency,
                confidence=rollup.confidence,
                observation_count=rollup.observation_count,
            )
            result.items.append(valued)
            result.total_cents += valued.total_cents
            result.valued_items += item.quantity
            confidences.append(rollup.confidence)

        # The weakest link. A total that is 90% `high` and 10% `low` is not a `high`-confidence
        # total, and rounding that up is the kind of flattery this product exists not to do.
        result.confidence = (
            min(confidences, key=_CONFIDENCE_ORDER.index) if confidences else "low"
        )
        return result

    @staticmethod
    def _unvaluable(item: InventoryItem) -> str | None:
        if item.is_graded:
            # Deliberate: the matcher collects no graded prices, so there is no basis. Saying so
            # is correct; valuing a slab at a raw median would be worse than not valuing it.
            return "graded"
        return None

    @staticmethod
    def _exclude(result: Valuation, item: InventoryItem, reason: str) -> None:
        result.unvalued_items += item.quantity
        result.unvalued_reasons[reason] = result.unvalued_reasons.get(reason, 0) + item.quantity
        # A count is informative; being able to see *which* ones is actionable, and it is usually
        # the same feedback loop the admin console has — an unpriced item is normally a printing
        # nothing has been seen selling.
        if len(result.unvalued_item_ids) < 500:
            result.unvalued_item_ids.append(item.id)
