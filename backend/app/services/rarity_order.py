"""Rarity ordering and primary-printing selection.

Pure, and deliberately shared: the same order drives the search row's "primary" printing, the
sort of the printings table, and the rarity material the UI renders. Two orderings would
eventually disagree, and the disagreement would show up as a card looking like a different
rarity depending on which screen you were on.
"""
from __future__ import annotations

from typing import Iterable, Protocol

#: Commonest first. `promo` sits last as its own category rather than a tier — a promo-only card
#: still needs a primary printing, and this ordering gives it one.
RARITY_ORDER: tuple[str, ...] = (
    "common", "uncommon", "rare", "holo_rare", "full_art",
    "alt_art", "prismatic", "secret", "promo",
)

_RANK = {rarity: index for index, rarity in enumerate(RARITY_ORDER)}


class _PrintingLike(Protocol):
    id: str
    rarity: str
    finish: str
    edition: str


def rarity_rank(rarity: str) -> int:
    """Unknown rarities sort last rather than raising — ranking is a display concern and must
    not be able to break a page. The importer already rejects unknown rarities at the door."""
    return _RANK.get(rarity, len(RARITY_ORDER))


def primary_printing(printings: Iterable[_PrintingLike]) -> _PrintingLike | None:
    """The printing a search row represents when a card has several.

    Lowest rarity tier, so the row reads as the common version a collector pictures. The
    `(finish, edition, id)` tail makes the choice deterministic: an unstable primary would make
    identical searches render differently, which is the same class of bug the total sort order
    exists to prevent.
    """
    candidates = list(printings)
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda p: (rarity_rank(p.rarity), p.finish, p.edition, p.id),
    )
