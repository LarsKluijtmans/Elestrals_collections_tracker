"""The wishlist — story 026.

Small, and carrying one decision that is easy to get wrong in a way users hate.

**Acquiring a wished printing does not clear the wish.** It offers to. A collector may want a second
copy, or a better condition, or a first edition of something they own unlimited — and silently
deleting their stated intent because a row appeared elsewhere destroys information they cannot get
back and did not agree to lose. So `acquired_but_still_wished` reports the overlap and the UI
prompts; nothing here removes anything on its own.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.inventory_item import InventoryItem
from ..models.printing import Printing
from ..models.wishlist_item import PRIORITIES, WishlistItem
from .inventory_service import InventoryError

MAX_QUANTITY = 1_000


class WishNotFound(InventoryError):
    code = "wishlist_item_not_found"
    status = 404


class AlreadyWished(InventoryError):
    code = "already_wished"
    status = 409


class InvalidWish(InventoryError):
    code = "bad_request"
    status = 400


@dataclass
class WishFields:
    desired_quantity: int | None = None
    priority: str | None = None
    max_price_cents: int | None = None
    max_price_currency: str | None = None
    notes: str | None = None


class WishlistService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_user(self, user_sub: str) -> list[WishlistItem]:
        return list(
            self._db.scalars(
                select(WishlistItem)
                .where(WishlistItem.user_sub == user_sub)
                .order_by(WishlistItem.created_at.desc())
            )
        )

    def add(
        self, user_sub: str, *, printing_id: str, desired_quantity: int = 1,
        priority: str = "normal", max_price_cents: int | None = None,
        max_price_currency: str | None = None, notes: str | None = None,
    ) -> WishlistItem:
        self._validate(
            desired_quantity=desired_quantity, priority=priority,
            max_price_cents=max_price_cents, max_price_currency=max_price_currency,
        )

        if self._db.get(Printing, printing_id) is None:
            raise InvalidWish(f"no such printing {printing_id!r}")

        # Checked here so the caller gets a 409 with a sentence rather than an IntegrityError with
        # a constraint name in it. The unique index is still what makes it true under concurrency.
        existing = self._db.scalar(
            select(WishlistItem).where(
                WishlistItem.user_sub == user_sub, WishlistItem.printing_id == printing_id
            )
        )
        if existing is not None:
            raise AlreadyWished("that printing is already on your wishlist")

        item = WishlistItem(
            user_sub=user_sub, printing_id=printing_id,
            desired_quantity=desired_quantity, priority=priority,
            max_price_cents=max_price_cents, max_price_currency=max_price_currency,
            notes=notes,
        )
        self._db.add(item)
        self._db.commit()
        return item

    def get(self, user_sub: str, item_id: str) -> WishlistItem:
        item = self._db.scalar(
            select(WishlistItem).where(
                WishlistItem.user_sub == user_sub, WishlistItem.id == item_id
            )
        )
        if item is None:
            raise WishNotFound(item_id)
        return item

    def edit(self, user_sub: str, item_id: str, fields: WishFields) -> WishlistItem:
        item = self.get(user_sub, item_id)

        # Validated against the *merged* state, not against the patch. Clearing only the currency
        # would otherwise leave a price with no currency behind — half a price, which the schema
        # refuses anyway but would refuse with an IntegrityError instead of a message.
        merged_cents = (
            fields.max_price_cents if fields.max_price_cents is not None else item.max_price_cents
        )
        merged_currency = (
            fields.max_price_currency if fields.max_price_currency is not None
            else item.max_price_currency
        )
        # `is not None`, not `or`. A patch setting `desired_quantity=0` is falsy, so `or` would
        # fall through to the stored value, validate *that*, and hand the 0 to the database —
        # where a CHECK constraint rejects it as an IntegrityError instead of a 400 with a
        # sentence. Caught by `test_editing_validates_the_merged_state_not_the_patch`.
        self._validate(
            desired_quantity=(
                fields.desired_quantity if fields.desired_quantity is not None
                else item.desired_quantity
            ),
            priority=fields.priority if fields.priority is not None else item.priority,
            max_price_cents=merged_cents,
            max_price_currency=merged_currency,
        )

        for name, value in vars(fields).items():
            if value is not None:
                setattr(item, name, value)
        self._db.commit()
        return item

    def remove(self, user_sub: str, item_id: str) -> None:
        item = self.get(user_sub, item_id)
        self._db.delete(item)
        self._db.commit()

    def acquired_but_still_wished(self, user_sub: str) -> list[WishlistItem]:
        """Wishes for printings the collector now owns.

        **Reported, never acted on.** This is what the UI prompts from; the wish clears only when
        somebody says so. Wanting a second copy is a legitimate thing to want, and a system that
        cannot tell "I got it" from "I got one of the two I wanted" should not be deleting either.
        """
        owned = select(InventoryItem.printing_id).where(InventoryItem.user_sub == user_sub)
        return list(
            self._db.scalars(
                select(WishlistItem).where(
                    WishlistItem.user_sub == user_sub,
                    WishlistItem.printing_id.in_(owned),
                )
            )
        )

    @staticmethod
    def _validate(
        *, desired_quantity: int, priority: str,
        max_price_cents: int | None, max_price_currency: str | None,
    ) -> None:
        if not (1 <= desired_quantity <= MAX_QUANTITY):
            raise InvalidWish(f"desired quantity must be between 1 and {MAX_QUANTITY}")
        if priority not in PRIORITIES:
            raise InvalidWish(f"unknown priority {priority!r}")
        # Both or neither. "500" is not money, and story 026 rejects a bare number outright.
        if (max_price_cents is None) != (max_price_currency is None):
            raise InvalidWish("a maximum price needs both an amount and a currency")
        if max_price_cents is not None and max_price_cents < 0:
            raise InvalidWish("a maximum price cannot be negative")
