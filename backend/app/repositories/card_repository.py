"""All database access for the Card aggregate (`cards` + their `printings`).

`save` is the **only** write path into the aggregate. Card and printings commit together, so a
card is never half-written — the failure mode this bolt exists to prevent.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.card import Card
from ..models.printing import Printing


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
