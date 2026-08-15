"""All database access for the Card aggregate (`cards` + their `printings`).

`save` is the **only** write path into the aggregate. Card and printings commit together, so a
card is never half-written — the failure mode this bolt exists to prevent.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import String, and_, case, func, or_, select
from sqlalchemy.orm import Session

from ..models.card import Card
from ..models.printing import Printing
from ..models.set import Set

#: Tier order from `ddd-01-domain-model.md`, lowest number ranks first.
MATCH_KINDS = {
    1: "exact_name",
    2: "name_prefix",
    3: "word_prefix",
    4: "collector_number",
    5: "set_code",
    6: "infix",
}

#: Below this, search returns nothing without touching the database. A one-character prefix
#: matches a third of the catalog — work thrown away before it renders.
MIN_TERM_LENGTH = 2


@dataclass
class SearchQuery:
    term: str = ""
    set_codes: list[str] = field(default_factory=list)
    elements: list[str] = field(default_factory=list)
    card_types: list[str] = field(default_factory=list)
    rarities: list[str] = field(default_factory=list)
    limit: int = 25
    offset: int = 0

    @property
    def is_searchable(self) -> bool:
        return len(self.term.strip()) >= MIN_TERM_LENGTH


def escape_like(term: str) -> str:
    """`%` and `_` are wildcards. A collector searching for `100%` means the characters."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class CardRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_natural_key(self, set_id: str, collector_number: str) -> Card | None:
        """Printings come with it — `Card.printings` is `lazy="selectin"`, so this is two
        queries, not one per card."""
        return self._db.scalar(
            select(Card).where(
                Card.set_id == set_id, Card.collector_number == collector_number
            )
        )

    def save(self, card: Card) -> Card:
        """Persist the whole aggregate in one transaction.

        Called only when something actually changed: an unchanged card never reaches here, so
        a re-import over unchanged sources issues no writes at all.
        """
        self._db.add(card)
        self._db.commit()
        return card

    def rollback(self) -> None:
        self._db.rollback()

    # --- read surface (bolt 003) ----------------------------------------------------

    def search(self, query: SearchQuery) -> tuple[list[tuple[Card, str]], int]:
        """Ranked search. Returns `[(card, match_kind), ...]` and the total match count.

        Tiering is a `CASE` expression rather than a relevance score, so the ordering is
        explicit, readable in the query, and assertable in a test — see ADR-002.
        """
        if not query.is_searchable:
            return [], 0

        term = query.term.strip().lower()
        safe = escape_like(term)
        prefix, word, infix = f"{safe}%", f"% {safe}%", f"%{safe}%"

        name = func.lower(Card.name)
        number = func.lower(Card.collector_number)
        set_code = func.lower(Set.code)

        tier = case(
            (name == term, 1),
            (name.like(prefix, escape="\\"), 2),
            (name.like(word, escape="\\"), 3),
            (number.like(prefix, escape="\\"), 4),
            (set_code == term, 5),
            else_=6,
        )

        matches = or_(
            name == term,
            name.like(infix, escape="\\"),
            number.like(prefix, escape="\\"),
            set_code == term,
        )

        stmt = select(Card, tier.label("tier")).join(Set, Set.id == Card.set_id).where(matches)
        stmt = self._apply_filters(stmt, query)

        total = self._db.scalar(
            select(func.count()).select_from(stmt.subquery())
        ) or 0

        # A total order. The trailing `Card.id` exists only to break exact ties: without it the
        # row under a keyboard cursor could move between render and Enter, and bolt 005's
        # fast-add would commit the wrong printing with no error raised anywhere.
        rows = self._db.execute(
            stmt.order_by(
                tier.asc(),
                func.coalesce(Set.released_on, func.cast("1900-01-01", String)).desc(),
                Card.collector_number.asc(),
                Card.id.asc(),
            )
            .limit(query.limit)
            .offset(query.offset)
        ).all()

        return [(row[0], MATCH_KINDS.get(row[1], "infix")) for row in rows], int(total)

    def _apply_filters(self, stmt, query: SearchQuery):
        """Repeated values OR within an attribute, distinct attributes AND across — the filter
        algebra in `api-conventions.md`, so URL-serialised UI filters cannot drift from it."""
        if query.set_codes:
            stmt = stmt.where(Set.code.in_(query.set_codes))
        if query.elements:
            stmt = stmt.where(Card.element.in_(query.elements))
        if query.card_types:
            stmt = stmt.where(Card.card_type.in_(query.card_types))
        if query.rarities:
            stmt = stmt.where(
                select(Printing.id)
                .where(and_(Printing.card_id == Card.id, Printing.rarity.in_(query.rarities)))
                .exists()
            )
        return stmt

    def detail(self, card_id: str) -> Card | None:
        return self._db.get(Card, card_id)

    def for_set_ordered(self, set_id: str, *, limit: int, offset: int) -> list[Card]:
        return list(
            self._db.scalars(
                select(Card)
                .where(Card.set_id == set_id)
                .order_by(Card.collector_number.asc())
                .limit(limit)
                .offset(offset)
            )
        )

    def collector_numbers_for_set(self, set_id: str) -> set[str]:
        """Drives coverage: distinct cards present, against the set's declared card_count."""
        return set(
            self._db.scalars(select(Card.collector_number).where(Card.set_id == set_id))
        )

    def count_for_set(self, set_id: str) -> int:
        return int(
            self._db.scalar(select(func.count(Card.id)).where(Card.set_id == set_id)) or 0
        )

    def count_printings_for_set(self, set_id: str) -> int:
        return int(
            self._db.scalar(
                select(func.count(Printing.id))
                .join(Card, Card.id == Printing.card_id)
                .where(Card.set_id == set_id)
            )
            or 0
        )
