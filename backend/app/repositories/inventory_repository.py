"""All database access for `inventory_items`.

**Every method takes `user_sub` first and required.** An unscoped query should be impossible to
write, not merely discouraged in review — so there is no `get(item_id)` on this class at all.
The only way to reach a row is through its owner.

Cross-user access returns `None`, which the service turns into a **404, never a 403**: telling
a stranger that an id exists but is not theirs is an enumeration oracle.
"""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..models.card import Card
from ..models.inventory_item import InventoryItem
from ..models.printing import Printing


class InventoryRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # --- reads ----------------------------------------------------------------------

    def get(self, user_sub: str, item_id: str) -> InventoryItem | None:
        return self._db.scalar(
            select(InventoryItem).where(
                InventoryItem.user_sub == user_sub, InventoryItem.id == item_id
            )
        )

    def find_mergeable(
        self, user_sub: str, printing_id: str, merge_condition: str | None
    ) -> InventoryItem | None:
        """The row a new ungraded add would merge into. `merge_condition is None` (graded)
        never matches, which is the point — `IS NULL` would match every graded row."""
        if merge_condition is None:
            return None
        return self._db.scalar(
            select(InventoryItem).where(
                InventoryItem.user_sub == user_sub,
                InventoryItem.printing_id == printing_id,
                InventoryItem.merge_condition == merge_condition,
            )
        )

    def list_for_user(
        self, user_sub: str, *, limit: int = 100, offset: int = 0,
        printing_id: str | None = None,
    ) -> list[InventoryItem]:
        """A minimal owner-scoped listing — enough to read back a write and drive edit/remove.

        The filtered, sorted, virtualised collection table is story 019 in bolt 006; its filter
        set (set, element, rarity, condition, finish, language, graded, for-trade) belongs
        there rather than half-built here.
        """
        stmt = (
            select(InventoryItem)
            .where(InventoryItem.user_sub == user_sub)
            .order_by(InventoryItem.created_at.desc(), InventoryItem.id.asc())
            .limit(limit)
            .offset(offset)
        )
        if printing_id:
            stmt = stmt.where(InventoryItem.printing_id == printing_id)
        return list(self._db.scalars(stmt))

    def all_for_user(self, user_sub: str, *, set_id: str | None = None) -> list[InventoryItem]:
        """Every holding, unpaged. The valuation path.

        Unpaged on purpose: a total computed over the first hundred rows is not a total, and
        showing one would be worse than showing nothing. The NFR bounds this at 5,000 holdings
        within 1.5s p95, and the cost that actually matters is the price lookup — which
        `PriceRepository.latest_for_printings` does in one query for the whole set.
        """
        stmt = select(InventoryItem).where(InventoryItem.user_sub == user_sub)
        if set_id:
            stmt = stmt.join(Printing, Printing.id == InventoryItem.printing_id).join(
                Card, Card.id == Printing.card_id
            ).where(Card.set_id == set_id)
        return list(self._db.scalars(stmt))

    def count_for_user(self, user_sub: str) -> int:
        return int(
            self._db.scalar(
                select(func.count(InventoryItem.id)).where(InventoryItem.user_sub == user_sub)
            ) or 0
        )

    def total_quantity(self, user_sub: str) -> int:
        return int(
            self._db.scalar(
                select(func.coalesce(func.sum(InventoryItem.quantity), 0))
                .where(InventoryItem.user_sub == user_sub)
            ) or 0
        )

    # --- writes ---------------------------------------------------------------------

    def upsert_merge(self, values: dict) -> None:
        """Insert, or add to the quantity of the row holding this merge key — in **one
        statement**.

        The fast-add flow fires concurrent requests by design. A read-then-write passes every
        sequential test and loses rows in production, so the database resolves the race against
        `uq_inventory_merge` rather than Python resolving it between two round trips.

        A graded row carries `merge_condition = NULL`, which never conflicts, so it always
        inserts — each graded copy stays an individually meaningful object.
        """
        table = InventoryItem.__table__
        dialect = self._db.get_bind().dialect.name

        if dialect == "mysql":
            stmt = mysql_insert(table).values(**values)
            stmt = stmt.on_duplicate_key_update(
                quantity=table.c.quantity + stmt.inserted.quantity,
                updated_at=values["updated_at"],
            )
        else:
            stmt = sqlite_insert(table).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_sub", "printing_id", "merge_condition"],
                set_={
                    "quantity": table.c.quantity + stmt.excluded.quantity,
                    "updated_at": values["updated_at"],
                },
            )
        self._db.execute(stmt)
        self._db.flush()
        # The upsert is a Core statement, so the ORM identity map still holds whatever
        # quantity it last loaded. Without this, reading the merged row back through the same
        # session returns the *pre-increment* value — the write is correct in the database and
        # wrong everywhere the caller can see it.
        self._db.expire_all()

    def find_twin(
        self, user_sub: str, printing_id: str, merge_condition: str | None, exclude_id: str
    ) -> InventoryItem | None:
        """The row an edited item would collide with, if any."""
        if merge_condition is None:
            return None
        return self._db.scalar(
            select(InventoryItem).where(
                InventoryItem.user_sub == user_sub,
                InventoryItem.printing_id == printing_id,
                InventoryItem.merge_condition == merge_condition,
                InventoryItem.id != exclude_id,
            )
        )

    def flush(self) -> None:
        self._db.flush()

    def commit(self) -> None:
        """The transaction boundary for an inventory write *and* its completion recompute.

        Exposed here rather than taken by the service, so `Session` stays inside the repository
        layer — the rule in tech-stack.md is that repositories are the only code that touches
        the database, and a service holding a session erodes it one call at a time.
        """
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()

    def increment(self, item: InventoryItem, by: int) -> InventoryItem:
        item.quantity = item.quantity + by
        self._db.flush()
        return item

    def remove(self, user_sub: str, item_id: str) -> bool:
        result = self._db.execute(
            delete(InventoryItem).where(
                InventoryItem.user_sub == user_sub, InventoryItem.id == item_id
            )
        )
        self._db.flush()
        return (result.rowcount or 0) > 0

    def set_ids_touched_by(self, printing_ids: list[str]) -> list[str]:
        """Which sets a group of printings belongs to — the scope a completion recompute needs."""
        if not printing_ids:
            return []
        return list(
            self._db.scalars(
                select(Card.set_id)
                .join(Printing, Printing.card_id == Card.id)
                .where(Printing.id.in_(printing_ids))
                .distinct()
            )
        )
