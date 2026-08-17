"""The closed vocabularies the matcher folds source spellings onto.

**A copy of phase 1's, deliberately** — the third one in this service, after `models/base.py` and
`core/security.py`, and for the same reason: the two services share conventions, not code.

The values are not arbitrary here; they must equal the ones `elestrals` stores, or a match writes
a `finish` the catalog does not have. What keeps them equal is that they describe the *same
physical cards*, and that this file says so. If phase 1 ever adds a rarity, this list needs the
same addition, and the drift shows up as matches that suddenly fall under the confidence floor —
loudly, in the console, rather than silently.

Every lookup returns `None` for an unrecognised value, and every caller turns that into a
rejection. An unmapped rarity is never silently defaulted to `common`: a wrong rarity is a wrong
SKU, which is a wrong price and a wrong valuation downstream.
"""
from __future__ import annotations

#: Mirrors `elestrals-api`'s `models/printing.py`.
RARITIES = (
    "common", "uncommon", "rare", "holo_rare", "full_art",
    "alt_art", "prismatic", "secret", "promo",
)
FINISHES = ("normal", "foil", "reverse_foil", "prismatic")
EDITIONS = ("unlimited", "first")

#: Mirrors `elestrals-api`'s `models/inventory_item.py`.
CONDITIONS = (
    "mint", "near_mint", "lightly_played", "moderately_played", "heavily_played", "damaged",
)

#: Mirrors `elestrals-api`'s `models/sealed_product.py`.
SEALED_KINDS = (
    "booster_pack", "booster_box", "starter_deck", "elite_box", "bundle", "case", "other",
)


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
