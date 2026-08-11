"""All database access for `set_completion`.

Like the inventory repository, every method takes `user_sub` first and required. Completion is
per-person data and there is no legitimate unscoped read of it.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.card import Card
from ..models.inventory_item import InventoryItem
from ..models.printing import Printing
from ..models.set import Set
from ..models.set_completion import SetCompletion


class SetCompletionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_user(self, user_sub: str) -> list[tuple[SetCompletion, Set]]:
        rows = self._db.execute(
            select(SetCompletion, Set)
            .join(Set, Set.id == SetCompletion.set_id)
            .where(SetCompletion.user_sub == user_sub)
            .order_by(Set.code)
        ).all()
        return [(row[0], row[1]) for row in rows]

    def get(self, user_sub: str, set_id: str) -> SetCompletion | None:
        return self._db.scalar(
            select(SetCompletion).where(
                SetCompletion.user_sub == user_sub, SetCompletion.set_id == set_id
            )
        )

    def measure(self, user_sub: str, set_id: str) -> tuple[int, int]:
        """Recompute from inventory: `(distinct cards owned, total copies)`.

        Distinct **cards**, not printings — 126 cards can carry 189 printings, and a ratio over
        the wrong denominator reads above 100%.
        """
        owned_cards = self._db.scalar(
            select(func.count(func.distinct(Card.id)))
            .select_from(InventoryItem)
            .join(Printing, Printing.id == InventoryItem.printing_id)
            .join(Card, Card.id == Printing.card_id)
            .where(InventoryItem.user_sub == user_sub, Card.set_id == set_id)
        ) or 0

        total_quantity = self._db.scalar(
            select(func.coalesce(func.sum(InventoryItem.quantity), 0))
            .select_from(InventoryItem)
            .join(Printing, Printing.id == InventoryItem.printing_id)
            .join(Card, Card.id == Printing.card_id)
            .where(InventoryItem.user_sub == user_sub, Card.set_id == set_id)
        ) or 0

        return int(owned_cards), int(total_quantity)

    def upsert(
        self, user_sub: str, set_id: str, *, owned_cards: int, card_count: int,
        total_quantity: int,
    ) -> SetCompletion:
        """No commit — the caller owns the transaction, so a failed recompute rolls the
        inventory write back with it."""
        row = self.get(user_sub, set_id)
        if row is None:
            row = SetCompletion(user_sub=user_sub, set_id=set_id)
            self._db.add(row)
        row.owned_cards = owned_cards
        row.card_count = card_count
        row.total_quantity = total_quantity
        self._db.flush()
        return row

    def all_set_ids(self) -> list[str]:
        return list(self._db.scalars(select(Set.id)))

    def user_subs_with_inventory(self) -> list[str]:
        return list(self._db.scalars(select(InventoryItem.user_sub).distinct()))
