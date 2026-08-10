"""All database access for `printings` outside the Card aggregate's own write path.

Writes to a printing as part of importing a card go through `CardRepository.save`; this
repository is for reads and for the price-tracking toggle phase 2 needs.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.card import Card
from ..models.printing import Printing


class PrintingRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, printing_id: str) -> Printing | None:
        return self._db.get(Printing, printing_id)

    def list_for_card(self, card_id: str) -> list[Printing]:
        return list(
            self._db.scalars(
                select(Printing)
                .where(Printing.card_id == card_id)
                .order_by(Printing.rarity, Printing.finish, Printing.edition)
            )
        )

    def list_for_cards(self, card_ids: list[str]) -> dict[str, list[Printing]]:
        """Batched: a 50-row search page costs two queries, not fifty-one."""
        if not card_ids:
            return {}
        rows = self._db.scalars(
            select(Printing).where(Printing.card_id.in_(card_ids))
        )
        grouped: dict[str, list[Printing]] = {card_id: [] for card_id in card_ids}
        for printing in rows:
            grouped.setdefault(printing.card_id, []).append(printing)
        return grouped

    def list_for_set(self, set_id: str) -> list[Printing]:
        return list(
            self._db.scalars(
                select(Printing)
                .join(Card, Card.id == Printing.card_id)
                .where(Card.set_id == set_id)
                .order_by(Card.collector_number)
            )
        )

    def set_price_tracking(self, printing_id: str, *, tracked: bool) -> Printing | None:
        row = self.get(printing_id)
        if row is None:
            return None
        row.is_tracked_for_price = tracked
        self._db.commit()
        return row
