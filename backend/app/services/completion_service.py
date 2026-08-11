"""Set completion — recomputed inside the caller's transaction, never after it.

A summary table that can drift from its source is worse than no summary table: a collector who
adds a card and sees the old number stops trusting every number on the page. So `recompute` does
not commit, and it does not schedule anything. It runs in the transaction that changed the
inventory, and if it fails that write rolls back with it.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..repositories.set_completion_repository import SetCompletionRepository
from ..repositories.set_repository import SetRepository


@dataclass(frozen=True, slots=True)
class CompletionView:
    set_code: str
    set_name: str
    owned_cards: int
    card_count: int
    total_quantity: int

    @property
    def ratio(self) -> float:
        """Guarded: a set with no declared printed size has no meaningful percentage, and
        `x/0` is not a number a UI can render."""
        return (self.owned_cards / self.card_count) if self.card_count else 0.0


class CompletionService:
    def __init__(self, completion: SetCompletionRepository, sets: SetRepository) -> None:
        self._completion = completion
        self._sets = sets

    def recompute(self, user_sub: str, set_ids: list[str]) -> None:
        """Recompute the given sets for one user. Flushes, never commits."""
        for set_id in dict.fromkeys(set_ids):  # de-duplicate, keep order
            set_row = self._sets.get(set_id)
            if set_row is None:
                continue
            owned_cards, total_quantity = self._completion.measure(user_sub, set_id)
            self._completion.upsert(
                user_sub, set_id,
                owned_cards=owned_cards,
                card_count=set_row.card_count,
                total_quantity=total_quantity,
            )

    def rebuild_for_user(self, user_sub: str) -> int:
        """Regenerate the whole projection for a user from inventory.

        The repair path. If the projection is ever wrong — a bad migration, a bug, a restore —
        this reconstructs it from the only source of truth there is.
        """
        set_ids = self._completion.all_set_ids()
        self.recompute(user_sub, set_ids)
        return len(set_ids)

    def view(self, user_sub: str) -> list[CompletionView]:
        return [
            CompletionView(
                set_code=set_row.code,
                set_name=set_row.name,
                owned_cards=row.owned_cards,
                card_count=row.card_count,
                total_quantity=row.total_quantity,
            )
            for row, set_row in self._completion.list_for_user(user_sub)
        ]
