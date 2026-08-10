"""Content fingerprints — the mechanism behind "second run: 0 added, 0 updated".

`INSERT ... ON DUPLICATE KEY UPDATE` cannot deliver that criterion on its own: if `updated_at`
sits in the UPDATE clause it changes on every run, so every row reports as *updated* and the
importer looks busy and idempotent at the same time — worse than looking broken.

So we compare content before writing. Equal fingerprint means no SQL is issued at all.

The hash covers only *meaningful* fields — never `id`, `created_at` or `updated_at`, which
would make every fingerprint unique by construction and defeat the whole point.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .canonical import CanonicalCard, CanonicalPrinting

#: Bump when the set of hashed fields changes, so a schema change forces one honest re-write
#: pass instead of silently reporting everything as unchanged.
FINGERPRINT_VERSION = "1"


def _digest(payload: list[Any]) -> str:
    # separators/sort_keys pinned: the hash must not drift with dict ordering or json defaults.
    blob = json.dumps(
        [FINGERPRINT_VERSION, *payload], sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def card_fingerprint(card: CanonicalCard) -> str:
    """Card-level fields only. Printings have their own fingerprints, so adding a printing
    does not mark the card itself as changed."""
    return _digest([
        card.set_code,
        card.collector_number,
        card.name,
        card.card_type,
        card.element,
        card.rune_type,
        card.subtype,
        card.attack,
        card.defence,
        card.spirit_cost,
        card.rules_text,
        card.flavour_text,
        card.artist,
    ])


def printing_fingerprint(printing: CanonicalPrinting) -> str:
    return _digest([
        printing.rarity,
        printing.finish,
        printing.language,
        printing.edition,
        printing.image_url,
        printing.is_tracked_for_price,
    ])
