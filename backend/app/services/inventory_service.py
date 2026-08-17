"""Inventory writes — add, edit, remove — with completion kept exact.

The invariant that decides whether this bolt works:

> **Adding the same ungraded printing twice produces one row with quantity 2, even when the two
> requests arrive at the same instant.**

The fast-add flow fires concurrent requests *by design* — a collector emptying a box types
faster than a round trip. A read-then-write implementation passes every sequential test and
loses rows in production, so the merge is a single atomic upsert against the
`(user_sub, printing_id, merge_condition)` unique index. The database decides the winner; this
service never checks-then-writes.

Graded copies carry `merge_condition = NULL`, which never conflicts, so each is its own row.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from ..models.inventory_item import CONDITIONS, InventoryItem
from ..repositories.inventory_repository import InventoryRepository
from ..repositories.printing_repository import PrintingRepository
from .completion_service import CompletionService


class InventoryError(Exception):
    """Base for errors the controller maps onto a stable error code."""

    code = "bad_request"
    status = 400


class PrintingNotFound(InventoryError):
    code = "printing_not_found"
    status = 404


class ItemNotFound(InventoryError):
    """Raised for someone else's item too — a 404, never a 403.

    Distinguishing "does not exist" from "not yours" hands a stranger an enumeration oracle
    over the whole inventory table.
    """

    code = "inventory_item_not_found"
    status = 404


class QuantityOutOfRange(InventoryError):
    code = "quantity_out_of_range"
    status = 400


class ItemChanged(InventoryError):
    """The holding moved since the caller last knew about it — ADR-005.

    A `409`, not a `404` and not a silent overwrite. Story 018 requires that undo refuses with an
    explanation rather than guessing, and this carries both numbers so the explanation can say
    what it expected and what it found.
    """

    code = "inventory_item_changed"
    status = 409

    def __init__(self, *, expected: int, actual: int) -> None:
        super().__init__("That holding changed since you added it")
        self.expected = expected
        self.actual = actual


class InvalidCondition(InventoryError):
    code = "bad_request"
    status = 400


MAX_QUANTITY = 10_000


@dataclass(frozen=True, slots=True)
class AddResult:
    item: InventoryItem
    merged: bool


@dataclass(frozen=True, slots=True)
class AdjustResult:
    item_id: str
    quantity: int
    #: True when the adjustment took the quantity to zero and the row went with it. Bolt 004:
    #: a zero-quantity row is a deletion that did not happen, so undoing the add that created a
    #: holding removes it rather than leaving a zero for the client to render.
    deleted: bool


@dataclass
class ItemFields:
    condition: str | None = None
    quantity: int | None = None
    is_graded: bool | None = None
    grader: str | None = None
    grade: float | None = None
    acquired_on: date | None = None
    acquired_unit_price_cents: int | None = None
    acquired_currency: str | None = None
    storage_location: str | None = None
    notes: str | None = None
    is_for_trade: bool | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InventoryService:
    def __init__(
        self,
        items: InventoryRepository,
        printings: PrintingRepository,
        completion: CompletionService,
    ) -> None:
        self._items = items
        self._printings = printings
        self._completion = completion

    # --- add -------------------------------------------------------------------------

    def add(
        self,
        user_sub: str,
        *,
        printing_id: str,
        condition: str = "near_mint",
        quantity: int = 1,
        is_graded: bool = False,
        grader: str | None = None,
        grade: float | None = None,
        **extra,
    ) -> AddResult:
        self._validate(condition=condition, quantity=quantity)
        if self._printings.get(printing_id) is None:
            raise PrintingNotFound(printing_id)

        merge_condition = InventoryItem.merge_key_for(condition=condition, is_graded=is_graded)
        new_id = str(uuid.uuid4())
        now = _now()

        values = {
            "id": new_id,
            "user_sub": user_sub,
            "printing_id": printing_id,
            "condition": condition,
            "quantity": quantity,
            "is_graded": is_graded,
            "grader": grader,
            "grade": grade,
            "merge_condition": merge_condition,
            "acquired_on": extra.get("acquired_on"),
            "acquired_unit_price_cents": extra.get("acquired_unit_price_cents"),
            "acquired_currency": extra.get("acquired_currency"),
            "storage_location": extra.get("storage_location"),
            "notes": extra.get("notes"),
            "is_for_trade": extra.get("is_for_trade", False),
            "created_at": now,
            "updated_at": now,
        }

        self._items.upsert_merge(values)

        # An ungraded add either inserted `new_id` or incremented the existing row; either way
        # the surviving row is the one holding this merge key.
        item = (
            self._items.find_mergeable(user_sub, printing_id, merge_condition)
            if merge_condition is not None
            else self._items.get(user_sub, new_id)
        )
        if item is None:  # pragma: no cover — the upsert just wrote it
            raise InventoryError("inventory write did not produce a row")

        self._recompute(user_sub, [printing_id])
        return AddResult(item=item, merged=item.id != new_id)

    # --- edit ------------------------------------------------------------------------

    def edit(self, user_sub: str, item_id: str, fields: ItemFields) -> InventoryItem:
        item = self._items.get(user_sub, item_id)
        if item is None:
            raise ItemNotFound(item_id)

        if fields.condition is not None:
            self._validate(condition=fields.condition)
        if fields.quantity is not None:
            self._validate(quantity=fields.quantity)

        for name in (
            "condition", "quantity", "is_graded", "grader", "grade", "acquired_on",
            "acquired_unit_price_cents", "acquired_currency", "storage_location",
            "notes", "is_for_trade",
        ):
            value = getattr(fields, name)
            if value is not None:
                setattr(item, name, value)

        item.merge_condition = InventoryItem.merge_key_for(
            condition=item.condition, is_graded=item.is_graded
        )

        # Editing a condition can collide with a row that already holds it. Merging is the
        # only coherent outcome: two ungraded Near Mint rows for one printing is precisely the
        # state the unique index exists to prevent.
        twin = self._items.find_twin(
            user_sub, item.printing_id, item.merge_condition, exclude_id=item.id
        )

        if twin is not None:
            twin.quantity = twin.quantity + item.quantity
            twin.updated_at = _now()
            self._items.remove(user_sub, item.id)
            item = twin
        else:
            item.updated_at = _now()

        self._items.flush()
        self._recompute(user_sub, [item.printing_id])
        return item

    # --- adjust (ADR-005) --------------------------------------------------------------

    def adjust(
        self, user_sub: str, item_id: str, *, delta: int, expected_quantity: int
    ) -> AdjustResult:
        """Change a quantity by `delta`, but only if it is still `expected_quantity`.

        The undo primitive. Story 018 requires that undo reverses **a delta, not a row** — so
        that undoing the second of three adds does not delete the holding — and that it
        **refuses rather than guesses** when the holding changed outside the session.

        `expected_quantity` is what makes both true at once, and it means *"what the caller
        believes, from its own record of what it did"*, not *"what the caller just read"*. A
        caller that fetches the row to fill this field has reinstated the read-then-write this
        endpoint exists to avoid, with extra steps and a false sense of safety. See ADR-005.

        The pre-read below is not a check-then-act: the atomic statement is still what decides,
        and this only exists to know the `printing_id` for the completion recompute and to tell
        a 404 from a 409 afterwards.
        """
        if delta == 0:
            raise QuantityOutOfRange("delta must not be zero")
        if abs(delta) > MAX_QUANTITY:
            raise QuantityOutOfRange(f"delta must be within ±{MAX_QUANTITY}")

        item = self._items.get(user_sub, item_id)
        if item is None:
            raise ItemNotFound(item_id)

        printing_id = item.printing_id
        target = expected_quantity + delta
        if target < 0:
            raise QuantityOutOfRange("that adjustment would take the quantity below zero")

        matched = self._items.compare_and_adjust(
            user_sub, item_id, delta=delta, expected=expected_quantity
        )
        if not matched:
            # Owner-scoped read, so reporting the actual quantity tells the caller only about a
            # row it already owns. A row that vanished between the two reads is a 404, which is
            # the same answer somebody else's row gets.
            current = self._items.get(user_sub, item_id)
            if current is None:
                raise ItemNotFound(item_id)
            raise ItemChanged(expected=expected_quantity, actual=current.quantity)

        self._recompute(user_sub, [printing_id])

        if target == 0:
            return AdjustResult(item_id=item_id, quantity=0, deleted=True)
        remaining = self._items.get(user_sub, item_id)
        return AdjustResult(
            item_id=item_id,
            quantity=remaining.quantity if remaining else target,
            deleted=False,
        )

    # --- remove ----------------------------------------------------------------------

    def remove(self, user_sub: str, item_id: str) -> None:
        item = self._items.get(user_sub, item_id)
        if item is None:
            raise ItemNotFound(item_id)

        printing_id = item.printing_id
        self._items.remove(user_sub, item_id)
        self._recompute(user_sub, [printing_id])

    # --- reads -----------------------------------------------------------------------

    def list_items(
        self, user_sub: str, *, limit: int = 100, offset: int = 0,
        printing_id: str | None = None,
    ) -> tuple[list[InventoryItem], int]:
        items = self._items.list_for_user(
            user_sub, limit=limit, offset=offset, printing_id=printing_id
        )
        return items, self._items.count_for_user(user_sub)

    def count(self, user_sub: str) -> int:
        return self._items.count_for_user(user_sub)

    def total_quantity(self, user_sub: str) -> int:
        return self._items.total_quantity(user_sub)

    # --- helpers ---------------------------------------------------------------------

    def _recompute(self, user_sub: str, printing_ids: list[str]) -> None:
        """Same transaction as the write. A failure here rolls the write back with it, which is
        the whole reason completion can never disagree with inventory."""
        set_ids = self._items.set_ids_touched_by(printing_ids)
        self._completion.recompute(user_sub, set_ids)
        self._items.commit()

    @staticmethod
    def _validate(*, condition: str | None = None, quantity: int | None = None) -> None:
        if condition is not None and condition not in CONDITIONS:
            raise InvalidCondition(f"unknown condition {condition!r}")
        if quantity is not None and not (1 <= quantity <= MAX_QUANTITY):
            raise QuantityOutOfRange(f"quantity must be between 1 and {MAX_QUANTITY}")
