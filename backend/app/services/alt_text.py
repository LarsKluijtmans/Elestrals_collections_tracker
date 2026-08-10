"""Alt text for card imagery.

`ux-guide.md` §9 makes this binding, not aspirational: every card image is
`"{name} — {set} {rarity}"`. It lives in one function so the search row, the set checklist, the
printings table and the card detail page cannot drift apart — three near-identical strings
assembled in three components is how an accessibility rule quietly stops being true.
"""
from __future__ import annotations

#: An em dash, as specified. Not a hyphen.
_SEPARATOR = " — "


def alt_for_printing(*, name: str, set_code: str, rarity: str) -> str:
    return f"{name}{_SEPARATOR}{set_code} {rarity}"


def alt_for_card(*, name: str, set_code: str, rarity: str | None) -> str:
    """A card with no printings has no rarity to name. That is a catalog defect the importer
    prevents, but a page must still render rather than 500 over alt text."""
    if not rarity:
        return f"{name}{_SEPARATOR}{set_code}"
    return alt_for_printing(name=name, set_code=set_code, rarity=rarity)
