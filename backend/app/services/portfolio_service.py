"""Portfolio history, P/L and slice valuation — stories 021, 022 and 033.

Three things were blocked on phase-1 work and are not any more: the history needed
`collection_snapshots`, the nightly valuation needed somewhere to write, and the slice needed
`/collection`'s filters. All three exist now, so this is the read side of them.

**The refusals matter more than the arithmetic here.**

*A holding with no cost basis is excluded from P/L and counted, never assumed to have cost zero.*
Assuming zero would report the entire market value as profit — wrong and flattering, which is the
worst combination a financial figure can be. Partial coverage is the normal case in phase 1, not an
edge case, so the covered proportion is always stated.

*A day with no rollup data gets a null value, and the chart breaks there.* Interpolating invents a
number; carrying today's price backwards makes the whole history move every night.

*Zero holdings is genuinely zero. Unpriced holdings are not.* Story 022 is explicit, and conflating
them either erases legitimate zeros or invents values.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..models.collection_snapshot import CollectionSnapshot
from ..models.inventory_item import InventoryItem
from ..repositories.inventory_repository import InventoryRepository
from ..repositories.price_repository import PriceRepository
from .valuation_service import ValuationService


@dataclass(frozen=True, slots=True)
class HistoryPoint:
    day: date
    item_count: int
    distinct_printings: int
    #: `None` means "not valued" — the chart breaks here rather than drawing a zero or a guess.
    total_value_cents: int | None
    currency: str
    confidence: str


@dataclass(frozen=True, slots=True)
class Performer:
    printing_id: str
    name: str
    set_code: str
    #: What this holding contributes to the total, in cents. Sorted on it, so a cheap card held
    #: in bulk can legitimately outrank an expensive single — which is usually the surprise.
    contribution_cents: int
    unit_cents: int
    quantity: int


@dataclass(frozen=True, slots=True)
class ProfitAndLoss:
    #: Over the holdings that *have* a cost basis, and only those.
    cost_cents: int
    market_cents: int
    #: Holdings counted in the two figures above.
    covered_items: int
    #: Holdings excluded because they have no cost basis. Counted, never assumed zero.
    uncovered_items: int

    @property
    def gain_cents(self) -> int:
        return self.market_cents - self.cost_cents

    @property
    def coverage(self) -> float:
        total = self.covered_items + self.uncovered_items
        return (self.covered_items / total) if total else 0.0


class PortfolioService:
    def __init__(self, items: InventoryRepository, prices: PriceRepository) -> None:
        self._items = items
        self._prices = prices

    # --- history (story 021) ---------------------------------------------------------

    def history(
        self, snapshots: list[CollectionSnapshot], *, currency: str = "EUR",
    ) -> list[HistoryPoint]:
        """The series a chart draws, straight off `collection_snapshots`.

        Days before any price data existed carry a null value. Story 021's last criterion: the
        chart starts where the *data* starts rather than drawing a flat line at zero back to the
        beginning of time — and the counts are still real history over that stretch.
        """
        return [
            HistoryPoint(
                day=row.taken_on,
                item_count=row.item_count,
                distinct_printings=row.distinct_printings,
                total_value_cents=row.total_value_cents,
                currency=row.currency or currency,
                confidence=row.valuation_confidence,
            )
            for row in snapshots
        ]

    # --- the nightly valuation (story 022) -------------------------------------------

    def value_snapshot(
        self, snapshot: CollectionSnapshot, holdings: list[InventoryItem], *,
        currency: str = "EUR",
    ) -> CollectionSnapshot:
        """Write a value onto one snapshot day, using **that day's** rollups.

        Not today's. Valuing history with current prices would make the entire chart move every
        night, which is the same failure as using today's FX rate for a year-old sale.

        Three outcomes, and the difference between the last two is the story's point:

        * holdings priced on that day → a value and a confidence
        * **no holdings at all → zero**, which is a true statement about an empty collection
        * holdings that nothing priced → **null**, because "we could not value this" is not "this
          was worth nothing"
        """
        if not holdings:
            snapshot.total_value_cents = 0
            snapshot.valuation_confidence = "none"
            snapshot.currency = currency
            return snapshot

        prices = self._prices.on_or_before(
            [h.printing_id for h in holdings], snapshot.taken_on, currency=currency,
        )
        valuation = ValuationService(self._prices).value_with(
            holdings, prices, currency=currency,
        )

        snapshot.currency = currency
        if valuation.valued_items == 0:
            # Nothing on that day had a price. Null, not zero — the chart breaks here, honestly.
            snapshot.total_value_cents = None
            snapshot.valuation_confidence = "none"
        else:
            snapshot.total_value_cents = valuation.total_cents
            snapshot.valuation_confidence = valuation.confidence
        return snapshot

    # --- P/L (story 021) --------------------------------------------------------------

    def profit_and_loss(
        self, holdings: list[InventoryItem], *, currency: str = "EUR",
    ) -> ProfitAndLoss:
        """Over the holdings that have a cost basis. **Only** those.

        A holding with no acquisition price is excluded and counted. Assuming zero would report
        the whole market value as profit, and a wrong number that flatters the reader is worse
        than no number at all.

        A cost recorded in another currency is also excluded rather than converted — FX
        normalisation is story 018's job, and converting here with an unspecified rate would be
        exactly the invented precision that story exists to prevent.
        """
        priced = self._prices.latest_for_printings(
            [h.printing_id for h in holdings], currency=currency,
        )

        cost = market = 0
        covered = uncovered = 0
        for item in holdings:
            basis = item.acquired_unit_price_cents
            if basis is None or (item.acquired_currency or currency) != currency:
                uncovered += 1
                continue
            # Exact condition first, then the unstated bucket — the same fallback
            # `ValuationService` uses. Never a *different* condition: a Heavily Played copy
            # priced at Near Mint is a wrong number with a plausible face.
            row = (priced.get((item.printing_id, item.condition or ""))
                   or priced.get((item.printing_id, "")))
            if row is None or row.median_cents is None:
                # It has a cost but no current price, so it cannot contribute a gain either way.
                uncovered += 1
                continue

            cost += basis * item.quantity
            market += int(row.median_cents) * item.quantity
            covered += 1

        return ProfitAndLoss(
            cost_cents=cost, market_cents=market,
            covered_items=covered, uncovered_items=uncovered,
        )

    # --- performers (story 021) -------------------------------------------------------

    def performers(
        self, holdings: list[InventoryItem], *, currency: str = "EUR", limit: int = 5,
    ) -> tuple[list[Performer], list[Performer]]:
        """`(best, worst)` by contribution to the total.

        Contribution rather than unit price, because that is the question being asked: a common
        held forty times can outrank a single expensive holo, and telling somebody their most
        valuable *card* when they asked what their collection is made of would be answering a
        different question.
        """
        priced = self._prices.latest_for_printings(
            [h.printing_id for h in holdings], currency=currency,
        )

        scored: list[Performer] = []
        for item in holdings:
            # Exact condition first, then the unstated bucket — the same fallback
            # `ValuationService` uses. Never a *different* condition: a Heavily Played copy
            # priced at Near Mint is a wrong number with a plausible face.
            row = (priced.get((item.printing_id, item.condition or ""))
                   or priced.get((item.printing_id, "")))
            if row is None or row.median_cents is None:
                continue
            printing = item.printing
            card = printing.card if printing else None
            set_row = card.set if card else None
            unit = int(row.median_cents)
            scored.append(Performer(
                printing_id=item.printing_id,
                name=card.name if card else "(unknown card)",
                set_code=set_row.code if set_row else "",
                contribution_cents=unit * item.quantity,
                unit_cents=unit,
                quantity=item.quantity,
            ))

        if not scored:
            return [], []

        scored.sort(key=lambda p: p.contribution_cents, reverse=True)
        # Parenthesised, because `a, b if cond else (x, y)` binds the ternary to `b` alone and
        # returns `(a, (x, y))` — a tuple that unpacks and then fails one line later. Caught by
        # `test_unpriced_holdings_do_not_appear_as_performers`.
        return scored[:limit], list(reversed(scored[-limit:]))
