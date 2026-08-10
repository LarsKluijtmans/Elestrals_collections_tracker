"""Assembling the catalog's read models — search, set browse, card detail.

One module because the three share the same projection helpers; splitting them would mean
three copies of `_printing_view` and, eventually, three subtly different alt-text strings.

Nothing here writes. These services take no `Principal` and touch no user table, which is what
makes `/cards` and `/sets` safely cacheable with no `Vary: Authorization`.
"""
from __future__ import annotations

from ..models.card import Card
from ..models.printing import Printing
from ..models.set import Set
from ..repositories.card_repository import CardRepository, SearchQuery
from ..repositories.printing_repository import PrintingRepository
from ..repositories.set_repository import SetRepository
from ..schemas import (
    CardDetailResponse,
    CardSearchResult,
    PrintingView,
    SetChecklistEntry,
    SetSummary,
)
from .alt_text import alt_for_printing
from .rarity_order import primary_printing, rarity_rank


def _printing_view(printing: Printing, *, card_name: str, set_code: str) -> PrintingView:
    return PrintingView(
        printing_id=printing.id,
        rarity=printing.rarity,
        finish=printing.finish,
        language=printing.language,
        edition=printing.edition,
        image_url=printing.image_url,
        alt_text=alt_for_printing(name=card_name, set_code=set_code, rarity=printing.rarity),
    )


def _ordered(printings: list[Printing]) -> list[Printing]:
    """Commonest first, then a deterministic tail — the same order everywhere a printing list
    is rendered."""
    return sorted(printings, key=lambda p: (rarity_rank(p.rarity), p.finish, p.edition, p.id))


def _set_summary(set_row: Set, imported_count: int) -> SetSummary:
    return SetSummary(
        code=set_row.code,
        name=set_row.name,
        series=set_row.series,
        released_on=set_row.released_on,
        card_count=set_row.card_count,
        imported_count=imported_count,
        logo_asset_url=set_row.logo_asset_url,
    )


class CardSearchService:
    def __init__(self, cards: CardRepository, printings: PrintingRepository) -> None:
        self._cards = cards
        self._printings = printings

    def search(self, query: SearchQuery) -> tuple[list[CardSearchResult], int]:
        matches, total = self._cards.search(query)
        if not matches:
            return [], total

        # Batched hydration: two queries for a page, not one per row.
        by_card = self._printings.list_for_cards([card.id for card, _ in matches])

        results: list[CardSearchResult] = []
        for card, match_kind in matches:
            printings = by_card.get(card.id, [])
            primary = primary_printing(printings)
            set_code = card.set.code if card.set else ""
            results.append(CardSearchResult(
                card_id=card.id,
                name=card.name,
                set_code=set_code,
                collector_number=card.collector_number,
                card_type=card.card_type,
                element=card.element,
                primary_printing=(
                    _printing_view(primary, card_name=card.name, set_code=set_code)
                    if primary else None
                ),
                printing_count=len(printings),
                match_kind=match_kind,
            ))
        return results, total


class CardDetailService:
    def __init__(self, cards: CardRepository, sets: SetRepository) -> None:
        self._cards = cards
        self._sets = sets

    def detail(self, card_id: str) -> CardDetailResponse | None:
        card: Card | None = self._cards.detail(card_id)
        if card is None:
            return None

        set_row = card.set
        set_code = set_row.code if set_row else ""
        return CardDetailResponse(
            card_id=card.id,
            name=card.name,
            set_code=set_code,
            set_name=set_row.name if set_row else "",
            collector_number=card.collector_number,
            card_type=card.card_type,
            element=card.element,
            rune_type=card.rune_type,
            subtype=card.subtype,
            attack=card.attack,
            defence=card.defence,
            spirit_cost=card.spirit_cost,
            rules_text=card.rules_text,
            flavour_text=card.flavour_text,
            artist=card.artist,
            printings=[
                _printing_view(p, card_name=card.name, set_code=set_code)
                for p in _ordered(list(card.printings))
            ],
        )


class SetBrowseService:
    def __init__(
        self,
        sets: SetRepository,
        cards: CardRepository,
        printings: PrintingRepository,
    ) -> None:
        self._sets = sets
        self._cards = cards
        self._printings = printings

    def list_sets(self, *, series: str | None = None) -> list[SetSummary]:
        return [_set_summary(s, count) for s, count in self._sets.summaries(series=series)]

    def checklist(
        self, set_code: str, *, limit: int, offset: int
    ) -> tuple[SetSummary, list[SetChecklistEntry], int] | None:
        set_row = self._sets.get_by_code(set_code)
        if set_row is None:
            return None

        imported = self._cards.count_for_set(set_row.id)
        cards = self._cards.for_set_ordered(set_row.id, limit=limit, offset=offset)
        by_card = self._printings.list_for_cards([c.id for c in cards])

        entries = [
            SetChecklistEntry(
                card_id=card.id,
                collector_number=card.collector_number,
                name=card.name,
                element=card.element,
                card_type=card.card_type,
                printings=[
                    _printing_view(p, card_name=card.name, set_code=set_row.code)
                    for p in _ordered(by_card.get(card.id, []))
                ],
            )
            for card in cards
        ]
        # `total` is the imported count, while `SetSummary.card_count` stays the declared
        # printed size. A checklist that quietly renumbered itself to what we hold would hide
        # exactly the gap the catalog is supposed to make visible.
        return _set_summary(set_row, imported), entries, imported
