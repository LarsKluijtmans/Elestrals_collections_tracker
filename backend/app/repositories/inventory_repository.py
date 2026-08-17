"""All database access for `inventory_items`.

**Every method takes `user_sub` first and required.** An unscoped query should be impossible to
write, not merely discouraged in review — so there is no `get(item_id)` on this class at all.
The only way to reach a row is through its owner.

Cross-user access returns `None`, which the service turns into a **404, never a 403**: telling
a stranger that an id exists but is not theirs is an enumeration oracle.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, delete, func, or_, select, update
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

    def compare_and_adjust(
        self, user_sub: str, item_id: str, *, delta: int, expected: int
    ) -> bool:
        """Change a quantity by `delta`, but only if it is still `expected`. **One statement.**

        ADR-005. Ownership and optimistic concurrency are the same `WHERE` clause, so there is no
        window between checking who owns the row and checking that nobody has moved it. The
        alternative — read, compare, write — is the race bolt 004's atomic upsert eliminated,
        reintroduced one layer up, and the undo path is where it would actually bite: the fast-add
        flow fires concurrent requests by design and a user can hold `Ctrl+Z`.

        Returns whether the row matched. `False` means wrong owner **or** stale expectation, and
        this method deliberately cannot tell you which — the caller resolves that with an
        owner-scoped read, so a stranger never learns that an id exists.

        Reaching zero **deletes** rather than updating: `quantity > 0` is a CHECK constraint, and
        bolt 004 is explicit that a zero-quantity row is a deletion that did not happen.
        """
        target = expected + delta
        if target < 0:
            return False

        scope = (
            InventoryItem.id == item_id,
            InventoryItem.user_sub == user_sub,
            InventoryItem.quantity == expected,
        )
        if target == 0:
            result = self._db.execute(delete(InventoryItem).where(*scope))
        else:
            result = self._db.execute(
                update(InventoryItem)
                .where(*scope)
                .values(quantity=InventoryItem.quantity + delta,
                        updated_at=datetime.now(timezone.utc))
            )
        self._db.flush()
        # The ORM identity map still holds the pre-update quantity; a caller reading the item
        # back through this session would see the old number. Same trap `upsert_merge` documents.
        self._db.expire_all()
        return (result.rowcount or 0) > 0

    # --- browse (bolt 006) ------------------------------------------------------------

    def _browse_stmt(self, user_sub: str, filters, *, sort: str):
        """The filtered selection, joined only as far as the filters and sort actually need.

        The join is conditional because the default view has no filters at all: an unfiltered
        collection answers from `inventory_items` off `ix_inventory_user_created_id`, and adding
        three joins to apply no predicate turns the seek every user's first page depends on into
        a scan.
        """
        from ..models.set import Set
        from ..services.collection_filters import SORTS_NEEDING_CARD

        stmt = select(InventoryItem)
        if filters.needs_catalog_join or sort in SORTS_NEEDING_CARD:
            stmt = (
                stmt.join(Printing, Printing.id == InventoryItem.printing_id)
                .join(Card, Card.id == Printing.card_id)
                .join(Set, Set.id == Card.set_id)
            )
        return stmt.where(filters.where(user_sub))

    def browse(
        self, user_sub: str, filters, *, sort: str, limit: int,
        after: tuple[str, ...] | None = None,
    ) -> list[InventoryItem]:
        """One page of the collection table, keyset-paged.

        `after` is the sort key of the last row of the previous page, not a count of rows to skip.
        That distinction is the whole point: a collector adding cards while scrolling shifts every
        offset underneath them, so an offset cursor silently repeats or skips rows. Neither shows
        up as an error — both show up as "the table is missing a card".
        """
        from ..services.collection_filters import SORTS

        order = SORTS.get(sort) or SORTS["added_desc"]
        stmt = self._browse_stmt(user_sub, filters, sort=sort).order_by(*order)

        if after is not None:
            stmt = stmt.where(self._keyset_predicate(sort, after))

        return list(self._db.scalars(stmt.limit(limit)))

    @staticmethod
    def _keyset_predicate(sort: str, after: tuple[str, ...]):
        """`(key OP last) OR (key = last AND id > last_id)` — a strict tuple comparison.

        Written out rather than using SQLAlchemy's `tuple_()`: MySQL optimises row-value
        comparisons well, SQLite supports them unevenly, and this runs on both. The `id` tie-break
        is what makes the order total — without it two rows created in the same millisecond can
        straddle a page boundary and one of them is never returned.
        """
        column, descending, cast = {
            "added_desc": (InventoryItem.created_at, True, datetime.fromisoformat),
            "added_asc": (InventoryItem.created_at, False, datetime.fromisoformat),
            "quantity_desc": (InventoryItem.quantity, True, int),
            "quantity_asc": (InventoryItem.quantity, False, int),
            "name_asc": (Card.name, False, str),
            "name_desc": (Card.name, True, str),
        }.get(sort, (InventoryItem.created_at, True, datetime.fromisoformat))

        key_raw, last_id = after
        try:
            key = cast(key_raw)
        except ValueError as exc:
            # A cursor whose key does not parse is a cursor from a different sort order. Loud,
            # so the client restarts at page 1 rather than being handed an arbitrary page.
            raise ValueError("malformed cursor") from exc

        beyond = column < key if descending else column > key
        return or_(beyond, and_(column == key, InventoryItem.id > last_id))

    @staticmethod
    def keyset_of(item: InventoryItem, sort: str) -> tuple[str, str]:
        """The cursor parts for a row — the inverse of `_keyset_predicate`'s decoding."""
        if sort in ("quantity_desc", "quantity_asc"):
            return (str(item.quantity), item.id)
        if sort in ("name_asc", "name_desc"):
            return (item.printing.card.name if item.printing else "", item.id)
        return (item.created_at.isoformat(), item.id)

    def count_matching(self, user_sub: str, filters) -> int:
        """The result count story 020 requires to be *always* visible.

        Counted rather than inferred from the page: "showing 50 of 50" when there are 4,000
        matches is the kind of wrong that makes someone believe they have lost cards.
        """
        stmt = self._browse_stmt(user_sub, filters, sort="added_desc")
        return int(
            self._db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        )

    def ids_matching(self, user_sub: str, filters, *, cap: int) -> list[str]:
        """Every id a filter selects, up to `cap`.

        Story 022: select-all over 10,000 rows is *the filter*, not 10,000 ids on the wire. The
        client sends the filter; this is where it becomes rows, once, server-side.
        """
        stmt = self._browse_stmt(user_sub, filters, sort="added_desc")
        return [
            row.id for row in self._db.scalars(
                stmt.order_by(InventoryItem.created_at.desc(), InventoryItem.id.asc()).limit(cap)
            )
        ]

    def distinct_printings(self, user_sub: str) -> int:
        return int(
            self._db.scalar(
                select(func.count(func.distinct(InventoryItem.printing_id)))
                .where(InventoryItem.user_sub == user_sub)
            ) or 0
        )

    def recent_activity(self, user_sub: str, *, limit: int = 10) -> list[InventoryItem]:
        """The dashboard's recent-changes list, ordered by *update* rather than creation — a
        quantity bumped this morning is more recent activity than a row created last week."""
        return list(
            self._db.scalars(
                select(InventoryItem)
                .where(InventoryItem.user_sub == user_sub)
                .order_by(InventoryItem.updated_at.desc(), InventoryItem.id.asc())
                .limit(limit)
            )
        )

    def owned_card_ids_in_set(self, user_sub: str, set_id: str) -> set[str]:
        """Cards in a set the user owns **any** printing of — story 024's definition of missing.

        Per card, not per printing: owning the common version means the card is not missing, even
        without the holo. The opposite reading turns a completed set into a permanently
        incomplete one, which is the number the dashboard ring would then disagree with.
        """
        return set(
            self._db.scalars(
                select(Card.id)
                .join(Printing, Printing.card_id == Card.id)
                .join(InventoryItem, InventoryItem.printing_id == Printing.id)
                .where(InventoryItem.user_sub == user_sub, Card.set_id == set_id)
                .distinct()
            )
        )

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
