"""Reading the collection — stories 019, 020 and 024.

Three things live here and nowhere else: the page (filtered, sorted, keyset-paged), the count that
must always be visible beside it, and the missing-cards answer.

**The count is a second query, deliberately.** Deriving "how many match" from the page is how a
table comes to say "50 of 50" when there are four thousand — and a collector who reads that
believes they have lost cards. One extra indexed count per request is a cheap price for a number
that is never wrong.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..core.pagination import decode_keyset, encode_keyset
from ..models.inventory_item import InventoryItem
from ..repositories.card_repository import CardRepository
from ..repositories.inventory_repository import InventoryRepository
from ..repositories.set_repository import SetRepository
from .collection_filters import DEFAULT_SORT, SORTS, FilterSet, InvalidFilter

#: Story 019's target is 10,000 rows browsable, not 10,000 rows in one response. The window is
#: what virtualization renders; the cursor is what makes the rest reachable.
MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50


@dataclass(frozen=True, slots=True)
class CollectionPage:
    items: list[InventoryItem]
    #: Total matching the filter, not the number returned. Story 020 requires it always visible.
    total: int
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class MissingCard:
    card_id: str
    collector_number: str
    name: str
    element: str | None
    rarity: str | None
    printing_id: str | None


@dataclass(frozen=True, slots=True)
class MissingReport:
    set_code: str
    set_name: str
    card_count: int
    owned_cards: int
    missing: list[MissingCard]


class CollectionBrowseService:
    def __init__(
        self,
        items: InventoryRepository,
        cards: CardRepository,
        sets: SetRepository,
    ) -> None:
        self._items = items
        self._cards = cards
        self._sets = sets

    def page(
        self, user_sub: str, filters: FilterSet, *,
        sort: str = DEFAULT_SORT, limit: int = DEFAULT_PAGE_SIZE, cursor: str | None = None,
    ) -> CollectionPage:
        if sort not in SORTS:
            raise InvalidFilter(f"unknown sort {sort!r}")
        limit = max(1, min(limit, MAX_PAGE_SIZE))

        after = decode_keyset(cursor, arity=2)

        # One more than asked for: whether a next page exists is answered by fetching the first
        # row of it, not by comparing against the total. The total is a separate query and can
        # legitimately have moved between the two — a collector adding cards is the normal case.
        rows = self._items.browse(user_sub, filters, sort=sort, limit=limit + 1, after=after)
        has_more = len(rows) > limit
        page = rows[:limit]

        next_cursor = None
        if has_more and page:
            next_cursor = encode_keyset(*self._items.keyset_of(page[-1], sort))

        return CollectionPage(
            items=page,
            total=self._items.count_matching(user_sub, filters),
            next_cursor=next_cursor,
        )

    def missing_from_set(self, user_sub: str, set_code: str) -> MissingReport | None:
        """Cards in a set the user owns no printing of — story 024.

        **Missing is per card, not per printing.** Owning the common version means the card is not
        missing even without the holo. The other reading makes a completed set permanently
        incomplete, and would put this view permanently at odds with the completion ring — two
        surfaces disagreeing about the same collection, which is worse than either being wrong
        alone.
        """
        set_row = self._sets.get_by_code(set_code)
        if set_row is None:
            return None

        owned = self._items.owned_card_ids_in_set(user_sub, set_row.id)
        # Unpaged, and bounded by a set being ~126 cards rather than by a limit. A *paged* missing
        # list would let a collector export "everything I am missing" and get one page of it.
        cards = self._cards.for_set_ordered(
            set_row.id, limit=self._cards.count_for_set(set_row.id) or 1, offset=0
        )

        missing = []
        for card in cards:
            if card.id in owned:
                continue
            printing = card.printings[0] if card.printings else None
            missing.append(MissingCard(
                card_id=card.id,
                collector_number=card.collector_number,
                name=card.name,
                element=card.element,
                rarity=printing.rarity if printing else None,
                printing_id=printing.id if printing else None,
            ))

        return MissingReport(
            set_code=set_row.code,
            set_name=set_row.name,
            # The *declared* printed size, so this agrees with the completion ring rather than
            # with however much of the set the catalog happens to hold. Coverage and completion
            # are different questions and the standards keep them apart on purpose.
            card_count=set_row.card_count,
            owned_cards=len(owned),
            missing=missing,
        )
