"""The public collection — story 033.

**A whitelist model, not a filtered one**, and the bolt notes are pedantic about this for a reason
worth restating: filtering fields out is a rule someone forgets to apply to the next field. Building
the response from a separate model that *never had* cost basis, acquisition price, storage location
or notes is a rule that enforces itself — a future column added to `inventory_items` cannot leak
here, because there is nowhere for it to go.

`PublicHolding` below has three fields plus catalog identity. That is the entire public surface.

**A private collection is a 404, not a 403.** Same rule as everywhere else: 403 confirms the handle
exists, which is an enumeration oracle over who has an account.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.inventory_item import InventoryItem
from ..models.user_profile import UserProfile

#: 43 chars of base64url — 256 bits. Long enough that guessing is not a strategy, and it is stored
#: in a `String(43)` column that will not silently truncate it.
SHARE_TOKEN_BYTES = 32


@dataclass(frozen=True, slots=True)
class PublicHolding:
    """**The whole public shape.**

    Note what is absent and cannot be added by accident: `acquired_unit_price_cents`,
    `acquired_on`, `acquired_currency`, `storage_location`, `notes`, `is_for_trade`. This model
    never had them, so no future refactor can forget to strip them.
    """

    printing_id: str
    card_id: str
    name: str
    set_code: str
    collector_number: str
    element: str | None
    rarity: str
    finish: str
    condition: str
    quantity: int


@dataclass(frozen=True, slots=True)
class PublicCollection:
    handle: str
    #: Total copies, and distinct printings. Both derived from what is already public.
    total_items: int
    distinct_printings: int
    holdings: list[PublicHolding]
    #: True when reached by share token rather than by handle — the page renders `noindex`.
    unlisted: bool


class PublicProfileService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def by_handle(self, handle: str) -> PublicCollection | None:
        """A `public` collection, by handle. `None` for anything else — the caller renders 404."""
        profile = self._db.scalar(
            select(UserProfile).where(UserProfile.handle == handle)
        )
        if profile is None or profile.collection_visibility != "public":
            # Includes `link`: a link-shared collection is deliberately *not* reachable by handle,
            # or the token would be pointless.
            return None
        return self._build(profile, unlisted=False)

    def by_share_token(self, token: str) -> PublicCollection | None:
        if not token:
            return None
        profile = self._db.scalar(
            select(UserProfile).where(UserProfile.share_token == token)
        )
        if profile is None or profile.collection_visibility not in ("link", "public"):
            return None
        return self._build(profile, unlisted=True)

    def rotate_share_token(self, profile: UserProfile) -> str:
        """Mint a new token, invalidating the old one.

        Rotation is the only revocation a shared link has. `token_urlsafe(32)` is 256 bits from
        the OS CSPRNG — not `uuid4()`, whose string form is guessable-adjacent and only 122 bits
        of entropy.
        """
        profile.share_token = secrets.token_urlsafe(SHARE_TOKEN_BYTES)
        self._db.commit()
        return profile.share_token

    def _build(self, profile: UserProfile, *, unlisted: bool) -> PublicCollection:
        items = list(self._db.scalars(
            select(InventoryItem)
            .where(InventoryItem.user_sub == profile.user_sub)
            .order_by(InventoryItem.created_at.desc())
        ))

        holdings = []
        for item in items:
            printing = item.printing
            card = printing.card if printing else None
            set_row = card.set if card else None
            # Constructed field by field into the whitelist model. There is no `**vars(item)`
            # here and there must never be — that is the line between a whitelist and a filter.
            holdings.append(PublicHolding(
                printing_id=item.printing_id,
                card_id=card.id if card else "",
                name=card.name if card else "(unknown card)",
                set_code=set_row.code if set_row else "",
                collector_number=card.collector_number if card else "",
                element=card.element if card else None,
                rarity=printing.rarity if printing else "",
                finish=printing.finish if printing else "",
                condition=item.condition,
                quantity=item.quantity,
            ))

        return PublicCollection(
            handle=profile.handle or "",
            total_items=sum(h.quantity for h in holdings),
            distinct_printings=len({h.printing_id for h in holdings}),
            holdings=holdings,
            unlisted=unlisted,
        )
