"""Bulk edit and bulk delete — story 022.

Two decisions carry this file, and both are in the story rather than invented here.

**A selection is a filter, not a list of ids.** "Select all" over 10,000 rows must not put 10,000
UUIDs on the wire; the client sends the filter it is already showing, and the server turns it into
rows once. A list of explicit ids is still accepted, because "these four" is also a real selection.

**Partial success is reported honestly.** All-or-nothing over 500 rows fails the whole operation
because one row moved, and a silent partial leaves a collector not knowing what happened to their
collection. So each row is attempted, failures are named with a reason, and the rest are applied.

That second decision is why this does not run inside one transaction. It is a deliberate trade and
worth stating plainly: a bulk edit is not atomic, and it is not meant to be — the report is what
makes it safe, not the rollback.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..repositories.inventory_repository import InventoryRepository
from .collection_filters import FilterSet
from .inventory_service import InventoryError, InventoryService, ItemFields

#: The largest selection a single request will act on. Above this the client must narrow the
#: filter — a bulk delete of a million rows is a different feature (and a different confirmation)
#: from the one this endpoint offers.
MAX_SELECTION = 5_000


class SelectionTooLarge(InventoryError):
    code = "selection_too_large"
    status = 400


@dataclass(frozen=True, slots=True)
class BulkFailure:
    item_id: str
    reason: str
    code: str


@dataclass
class BulkResult:
    requested: int = 0
    applied: int = 0
    failures: list[BulkFailure] = field(default_factory=list)

    @property
    def partial(self) -> bool:
        return bool(self.failures) and self.applied > 0


class BulkService:
    def __init__(self, items: InventoryRepository, inventory: InventoryService) -> None:
        self._items = items
        self._inventory = inventory

    def resolve(
        self, user_sub: str, *, item_ids: list[str] | None, filters: FilterSet | None
    ) -> list[str]:
        """Turn a selection into ids — from an explicit list, or by running the filter.

        `cap=MAX_SELECTION + 1` so the overflow is *detected* rather than silently truncated.
        Truncating would apply the operation to an arbitrary 5,000 of a larger selection and
        report success, which is the worst available outcome.
        """
        if item_ids:
            if len(item_ids) > MAX_SELECTION:
                raise SelectionTooLarge(
                    f"at most {MAX_SELECTION} items per request; narrow the selection"
                )
            # Deduplicated, and order preserved so the failure report reads in the order the
            # caller sent.
            return list(dict.fromkeys(item_ids))

        if filters is None:
            return []

        ids = self._items.ids_matching(user_sub, filters, cap=MAX_SELECTION + 1)
        if len(ids) > MAX_SELECTION:
            raise SelectionTooLarge(
                f"that filter selects more than {MAX_SELECTION} items; narrow it first"
            )
        return ids

    def edit(self, user_sub: str, ids: list[str], fields_: ItemFields) -> BulkResult:
        """Apply the same field changes to every selected row.

        Each row is its own attempt. A row deleted in another tab between selection and action
        fails as a 404 *for that row* and is named in the report; the others still apply. Story
        022's edge-case table asks for exactly this.
        """
        result = BulkResult(requested=len(ids))
        for item_id in ids:
            try:
                self._inventory.edit(user_sub, item_id, fields_)
            except InventoryError as exc:
                result.failures.append(
                    BulkFailure(item_id=item_id, reason=str(exc) or exc.code, code=exc.code)
                )
            else:
                result.applied += 1
        return result

    def delete(self, user_sub: str, ids: list[str]) -> BulkResult:
        result = BulkResult(requested=len(ids))
        for item_id in ids:
            try:
                self._inventory.remove(user_sub, item_id)
            except InventoryError as exc:
                result.failures.append(
                    BulkFailure(item_id=item_id, reason=str(exc) or exc.code, code=exc.code)
                )
            else:
                result.applied += 1
        return result
