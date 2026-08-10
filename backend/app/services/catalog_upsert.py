"""Idempotent write of one canonical card into the catalog.

The bolt's success criterion is *"second run over unchanged sources: 0 added, 0 updated"*, and
this module is where that is either true or a lie. The mechanism is a content fingerprint
compared **before** any write: an unchanged card issues no SQL at all, so a re-import over an
unchanged seed is pure reads.

See `ddd-02-technical-design.md` § Idempotency.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..importer.canonical import CanonicalCard, CanonicalPrinting
from ..importer.fingerprint import card_fingerprint, printing_fingerprint
from ..models.card import Card
from ..models.printing import Printing
from ..repositories.card_repository import CardRepository

ADDED = "added"
UPDATED = "updated"
UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class UpsertResult:
    outcome: str
    printings_added: int = 0
    printings_updated: int = 0


def _printing_key(p: Printing | CanonicalPrinting) -> tuple[str, str, str, str]:
    return (p.rarity, p.finish, p.language, p.edition)


class CatalogUpsert:
    def __init__(self, cards: CardRepository) -> None:
        self._cards = cards

    def upsert(self, canonical: CanonicalCard, *, set_id: str) -> UpsertResult:
        existing = self._cards.get_by_natural_key(set_id, canonical.collector_number)
        if existing is None:
            return self._insert(canonical, set_id=set_id)
        return self._merge(canonical, existing)

    def _insert(self, canonical: CanonicalCard, *, set_id: str) -> UpsertResult:
        card = Card(
            set_id=set_id,
            collector_number=canonical.collector_number,
            name=canonical.name,
            card_type=canonical.card_type,
            element=canonical.element,
            rune_type=canonical.rune_type,
            subtype=canonical.subtype,
            attack=canonical.attack,
            defence=canonical.defence,
            spirit_cost=canonical.spirit_cost,
            rules_text=canonical.rules_text,
            flavour_text=canonical.flavour_text,
            artist=canonical.artist,
            content_fingerprint=card_fingerprint(canonical),
        )
        for printing in canonical.printings:
            card.printings.append(self._new_printing(printing))

        self._cards.save(card)
        return UpsertResult(outcome=ADDED, printings_added=len(canonical.printings))

    def _merge(self, canonical: CanonicalCard, existing: Card) -> UpsertResult:
        changed = False

        # --- card level -------------------------------------------------------------
        new_fp = card_fingerprint(canonical)
        if existing.content_fingerprint != new_fp:
            existing.name = canonical.name
            existing.card_type = canonical.card_type
            existing.element = canonical.element
            existing.rune_type = canonical.rune_type
            existing.subtype = canonical.subtype
            existing.attack = canonical.attack
            existing.defence = canonical.defence
            existing.spirit_cost = canonical.spirit_cost
            existing.rules_text = canonical.rules_text
            existing.flavour_text = canonical.flavour_text
            existing.artist = canonical.artist
            existing.content_fingerprint = new_fp
            changed = True

        # --- printings --------------------------------------------------------------
        by_key = {_printing_key(p): p for p in existing.printings}
        added = 0
        updated = 0

        for canonical_printing in canonical.printings:
            key = _printing_key(canonical_printing)
            current = by_key.get(key)
            if current is None:
                existing.printings.append(self._new_printing(canonical_printing))
                added += 1
                changed = True
                continue

            printing_fp = printing_fingerprint(canonical_printing)
            if current.content_fingerprint != printing_fp:
                current.image_url = canonical_printing.image_url
                current.is_tracked_for_price = canonical_printing.is_tracked_for_price
                current.content_fingerprint = printing_fp
                updated += 1
                changed = True

        # A printing present in the catalog but absent from the source is deliberately left
        # alone. Sources are incomplete far more often than cards are unprinted, and inventory
        # rows point at printings — deleting one would orphan somebody's collection.

        if not changed:
            # The whole point: no save(), so no SQL.
            return UpsertResult(outcome=UNCHANGED)

        self._cards.save(existing)
        return UpsertResult(outcome=UPDATED, printings_added=added, printings_updated=updated)

    @staticmethod
    def _new_printing(canonical: CanonicalPrinting) -> Printing:
        return Printing(
            rarity=canonical.rarity,
            finish=canonical.finish,
            language=canonical.language,
            edition=canonical.edition,
            image_url=canonical.image_url,
            is_tracked_for_price=canonical.is_tracked_for_price,
            content_fingerprint=printing_fingerprint(canonical),
        )
