"""Closed vocabularies for the fields a source can get wrong.

Every lookup here returns `None` for an unrecognised value, and every caller turns that into
a **rejection**. An unmapped rarity is never silently defaulted to `common`: a wrong rarity is
a wrong SKU, which is a wrong price and a wrong completion count downstream.
"""
from __future__ import annotations

from ..models.card import CARD_TYPES, ELEMENTS, RUNE_TYPES
from ..models.printing import EDITIONS, FINISHES, RARITIES


def _slug(value: str) -> str:
    """Fold source spelling onto our snake_case vocabulary: 'Holo Rare' -> 'holo_rare'."""
    return "_".join(value.strip().lower().replace("-", " ").replace("/", " ").split())


#: Source spellings we accept beyond the canonical value itself.
_RARITY_ALIASES = {
    "holo": "holo_rare",
    "holofoil_rare": "holo_rare",
    "fullart": "full_art",
    "full_art_rare": "full_art",
    "alternate_art": "alt_art",
    "altart": "alt_art",
    "secret_rare": "secret",
    "promotional": "promo",
    "stellar": "prismatic",
}

_FINISH_ALIASES = {
    "holo": "foil",
    "holofoil": "foil",
    "foilcanvas": "foil",
    "reverse": "reverse_foil",
    "reverse_holo": "reverse_foil",
    "non_foil": "normal",
    "nonfoil": "normal",
    "standard": "normal",
}

_EDITION_ALIASES = {
    "1st": "first",
    "1st_edition": "first",
    "first_edition": "first",
    "unlimited_edition": "unlimited",
}

_CARD_TYPE_ALIASES = {
    "elestrals": "elestral",
    "spirits": "spirit",
    "runes": "rune",
}


def _lookup(value: str | None, allowed: tuple[str, ...], aliases: dict[str, str]) -> str | None:
    if value is None:
        return None
    slug = _slug(value)
    if not slug:
        return None
    slug = aliases.get(slug, slug)
    return slug if slug in allowed else None


def rarity(value: str | None) -> str | None:
    return _lookup(value, RARITIES, _RARITY_ALIASES)


def finish(value: str | None) -> str | None:
    return _lookup(value, FINISHES, _FINISH_ALIASES)


def edition(value: str | None) -> str | None:
    return _lookup(value, EDITIONS, _EDITION_ALIASES)


def card_type(value: str | None) -> str | None:
    return _lookup(value, CARD_TYPES, _CARD_TYPE_ALIASES)


def element(value: str | None) -> str | None:
    return _lookup(value, ELEMENTS, {})


def rune_type(value: str | None) -> str | None:
    return _lookup(value, RUNE_TYPES, {})


def default_edition_for_set(set_code: str) -> str:
    """`FE` is the First Edition series; everything else is unlimited unless stated.

    Applied by the adapter as a *default for a missing column*, never by the normaliser as a
    guess for a value it failed to recognise.
    """
    return "first" if set_code.upper().startswith("FE") else "unlimited"
