"""Sealed inventory — story 025.

Everything here mirrors bolt 004's inventory patterns: owner-scoped reads, a merge on add, **404
rather than 403** for someone else's row. What is different is one refusal.

**Marking a box opened creates no singles.** Not "not yet", not "behind a flag" — never. A booster
box has an expected distribution and an actual pull, and they are never the same, so generated cards
would be wrong every single time. Worse, they would be wrong in a way the collector has to find and
correct card by card, having first noticed that their collection contains cards they do not own.
The flag flips. That is the entire operation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.sealed_inventory_item import SealedInventoryItem
from ..models.sealed_product import SealedProduct
from .inventory_service import InventoryError

MAX_QUANTITY = 10_000


class SealedProductNotFound(InventoryError):
    code = "sealed_product_not_found"
    status = 404


class SealedItemNotFound(InventoryError):
    code = "sealed_item_not_found"
    status = 404


class SealedQuantityOutOfRange(InventoryError):
    code = "bad_request"
    status = 400


@dataclass
class SealedFields:
    acquired_on: date | None = None
    acquired_unit_price_cents: int | None = None
    acquired_currency: str | None = None
    storage_location: str | None = None
    notes: str | None = None
    quantity: int | None = None


@dataclass(frozen=True, slots=True)
class SealedAddResult:
    item: SealedInventoryItem
    merged: bool


class SealedService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_user(self, user_sub: str) -> list[SealedInventoryItem]:
        return list(
            self._db.scalars(
                select(SealedInventoryItem)
                .where(SealedInventoryItem.user_sub == user_sub)
                .order_by(SealedInventoryItem.created_at.desc())
            )
        )

    def add(
        self, user_sub: str, *, sealed_product_id: str, quantity: int = 1,
        is_sealed: bool = True, fields: SealedFields | None = None,
    ) -> SealedAddResult:
        """Add sealed product, merging into an existing holding in the same state.

        Sealed and opened copies of one product are different holdings — `is_sealed` is part of the
        unique key — so adding a sealed box when you already have an opened one creates a second
        row rather than confusing the two.
        """
        if not (1 <= quantity <= MAX_QUANTITY):
            raise SealedQuantityOutOfRange(f"quantity must be between 1 and {MAX_QUANTITY}")

        product = self._db.get(SealedProduct, sealed_product_id)
        if product is None:
            raise SealedProductNotFound(sealed_product_id)

        existing = self._db.scalar(
            select(SealedInventoryItem).where(
                SealedInventoryItem.user_sub == user_sub,
                SealedInventoryItem.sealed_product_id == sealed_product_id,
                SealedInventoryItem.is_sealed.is_(is_sealed),
            )
        )
        if existing is not None:
            existing.quantity += quantity
            self._db.commit()
            return SealedAddResult(item=existing, merged=True)

        item = SealedInventoryItem(
            user_sub=user_sub,
            sealed_product_id=sealed_product_id,
            quantity=quantity,
            is_sealed=is_sealed,
            **{k: v for k, v in vars(fields or SealedFields()).items()
               if k != "quantity" and v is not None},
        )
        self._db.add(item)
        self._db.commit()
        return SealedAddResult(item=item, merged=False)

    def get(self, user_sub: str, item_id: str) -> SealedInventoryItem:
        item = self._db.scalar(
            select(SealedInventoryItem).where(
                SealedInventoryItem.user_sub == user_sub, SealedInventoryItem.id == item_id
            )
        )
        if item is None:
            raise SealedItemNotFound(item_id)
        return item

    def open(self, user_sub: str, item_id: str, *, quantity: int = 1) -> SealedInventoryItem:
        """Mark copies opened. **Creates no singles.**

        Opening moves copies from the sealed holding to the opened one, merging if an opened
        holding already exists. Opening every copy removes the sealed row rather than leaving a
        zero — the same rule `inventory_items` follows, because a zero-quantity holding is a
        deletion that did not happen.

        Idempotent in the sense story 025 asks for: opening an already-opened holding is a no-op
        rather than an error, since the requested end state is already true.
        """
        item = self.get(user_sub, item_id)
        if not item.is_sealed:
            return item

        quantity = max(1, min(quantity, item.quantity))

        opened = self._db.scalar(
            select(SealedInventoryItem).where(
                SealedInventoryItem.user_sub == user_sub,
                SealedInventoryItem.sealed_product_id == item.sealed_product_id,
                SealedInventoryItem.is_sealed.is_(False),
            )
        )

        if quantity == item.quantity and opened is None:
            # The whole holding: flip it in place rather than delete-and-recreate, so the id,
            # cost basis and acquisition date survive.
            item.is_sealed = False
            self._db.commit()
            return item

        if opened is None:
            opened = SealedInventoryItem(
                user_sub=user_sub,
                sealed_product_id=item.sealed_product_id,
                quantity=0,
                is_sealed=False,
                acquired_on=item.acquired_on,
                acquired_unit_price_cents=item.acquired_unit_price_cents,
                acquired_currency=item.acquired_currency,
                storage_location=item.storage_location,
            )
            self._db.add(opened)

        opened.quantity += quantity
        item.quantity -= quantity
        if item.quantity == 0:
            self._db.delete(item)
        self._db.commit()
        return opened

    def edit(self, user_sub: str, item_id: str, fields: SealedFields) -> SealedInventoryItem:
        item = self.get(user_sub, item_id)
        if fields.quantity is not None:
            if not (1 <= fields.quantity <= MAX_QUANTITY):
                raise SealedQuantityOutOfRange(
                    f"quantity must be between 1 and {MAX_QUANTITY}"
                )
            item.quantity = fields.quantity
        for name, value in vars(fields).items():
            if name != "quantity" and value is not None:
                setattr(item, name, value)
        self._db.commit()
        return item

    def remove(self, user_sub: str, item_id: str) -> None:
        item = self.get(user_sub, item_id)
        self._db.delete(item)
        self._db.commit()
