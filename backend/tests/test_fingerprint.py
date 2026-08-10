"""Fingerprints must be stable across runs and sensitive to every meaningful field."""
from __future__ import annotations

from dataclasses import replace

from app.importer.canonical import CanonicalCard, CanonicalPrinting
from app.importer.fingerprint import card_fingerprint, printing_fingerprint


def card(**overrides) -> CanonicalCard:
    fields = {
        "set_code": "FE01", "collector_number": "BS1-001", "name": "Teratlas",
        "card_type": "elestral", "element": "earth", "attack": 2400, "defence": 2100,
        "spirit_cost": {"earth": 2}, "printings": (),
    }
    fields.update(overrides)
    return CanonicalCard(**fields)


def test_identical_cards_hash_identically():
    assert card_fingerprint(card()) == card_fingerprint(card())


def test_spirit_cost_key_order_does_not_change_the_hash():
    """Otherwise a re-serialised source would look changed on every run."""
    a = card(spirit_cost={"earth": 2, "fire": 1})
    b = card(spirit_cost={"fire": 1, "earth": 2})
    assert card_fingerprint(a) == card_fingerprint(b)


def test_each_meaningful_field_changes_the_hash():
    base = card_fingerprint(card())
    for field, value in [
        ("name", "Vipyro"), ("card_type", "spirit"), ("element", "fire"),
        ("attack", 2401), ("defence", 2), ("spirit_cost", {"earth": 3}),
        ("subtype", "x"), ("rules_text", "y"), ("flavour_text", "z"), ("artist", "a"),
        ("collector_number", "BS1-002"), ("set_code", "FE02"),
    ]:
        assert card_fingerprint(card(**{field: value})) != base, field


def test_printings_do_not_affect_the_card_fingerprint():
    """Per-entity scope: adding a printing must not mark the card itself as changed."""
    with_printing = card(printings=(
        CanonicalPrinting(rarity="rare", finish="normal", language="en", edition="first"),
    ))
    assert card_fingerprint(with_printing) == card_fingerprint(card())


def test_printing_fields_change_the_printing_fingerprint():
    base = CanonicalPrinting(rarity="rare", finish="normal", language="en", edition="first")
    assert printing_fingerprint(base) == printing_fingerprint(base)

    for field, value in [
        ("rarity", "holo_rare"), ("finish", "foil"), ("language", "nl"),
        ("edition", "unlimited"), ("image_url", "https://example.test/x.png"),
        ("is_tracked_for_price", False),
    ]:
        other = replace(base, **{field: value})
        assert printing_fingerprint(other) != printing_fingerprint(base), field
