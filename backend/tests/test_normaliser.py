"""The normaliser is pure and total: no database, no network, and it never raises.

Every test here is fixture-driven, which is exactly what the unit brief requires per source.
"""
from __future__ import annotations

from app.importer.canonical import RawRecord
from app.importer.normaliser import normalise_set

BASE = {
    "set_code": "FE01",
    "collector_number": "BS1-001",
    "name": "Teratlas",
    "card_type": "elestral",
    "element": "earth",
    "rune_type": "",
    "subtype": "",
    "attack": "2400",
    "defence": "2100",
    "spirit_cost": '{"earth": 2}',
    "rarity": "holo_rare",
    "finish": "foil",
    "language": "en",
    "edition": "first",
    "image_url": "",
}


def row(**overrides) -> RawRecord:
    data = {**BASE, **{k: str(v) for k, v in overrides.items()}}
    ref = overrides.pop("_ref", "FE01.csv:2")
    return RawRecord(source_ref=str(ref), data=data)


def only_rejection(result):
    assert not result.cards, "expected no cards to be emitted"
    assert len(result.rejections) == 1
    return result.rejections[0]


def test_single_row_becomes_one_card_with_one_printing():
    result = normalise_set([row()], set_code="FE01")
    assert not result.rejections
    (card,) = result.cards
    assert card.name == "Teratlas"
    assert card.card_type == "elestral"
    assert card.attack == 2400
    assert card.spirit_cost == {"earth": 2}
    assert len(card.printings) == 1
    assert card.printings[0].rarity == "holo_rare"


def test_rows_sharing_a_collector_number_group_into_one_card():
    result = normalise_set(
        [row(), row(rarity="rare", finish="normal")], set_code="FE01"
    )
    assert not result.rejections
    (card,) = result.cards
    assert len(card.printings) == 2
    assert {p.rarity for p in card.printings} == {"holo_rare", "rare"}


def test_vocabulary_aliases_are_folded():
    result = normalise_set([row(rarity="Holo Rare", finish="Holofoil")], set_code="FE01")
    (card,) = result.cards
    assert card.printings[0].rarity == "holo_rare"
    assert card.printings[0].finish == "foil"


def test_unknown_rarity_rejects_the_card_rather_than_defaulting():
    """A wrong rarity is a wrong SKU, a wrong price and a wrong completion count."""
    rejection = only_rejection(normalise_set([row(rarity="ultra_mega")], set_code="FE01"))
    assert rejection.reason_code == "unknown_rarity"
    assert rejection.field == "rarity"


def test_unknown_finish_is_rejected():
    rejection = only_rejection(normalise_set([row(finish="sparkly")], set_code="FE01"))
    assert rejection.reason_code == "unknown_finish"


def test_unknown_edition_is_rejected():
    rejection = only_rejection(normalise_set([row(edition="third")], set_code="FE01"))
    assert rejection.reason_code == "unknown_edition"


def test_one_bad_printing_rejects_the_whole_card():
    """Importing a card with a printing missing silently corrupts set completion, so the
    whole card goes rather than the offending row alone."""
    result = normalise_set(
        [row(), row(rarity="not_a_rarity", finish="normal")], set_code="FE01"
    )
    assert not result.cards
    assert result.rejections[0].reason_code == "unknown_rarity"


def test_conflicting_card_level_fields_reject_the_card():
    """Taking the first row would make the card depend on file ordering."""
    result = normalise_set(
        [row(), row(rarity="rare", finish="normal", attack=9999, _ref="FE01.csv:3")],
        set_code="FE01",
    )
    rejection = only_rejection(result)
    assert rejection.reason_code == "conflicting_card_fields"
    assert rejection.field == "attack"
    assert "2400" in rejection.message and "9999" in rejection.message


def test_duplicate_printing_key_within_a_file_is_rejected():
    result = normalise_set([row(), row()], set_code="FE01")
    rejection = only_rejection(result)
    assert rejection.reason_code == "duplicate_printing_key"


def test_missing_collector_number_rejects_the_row_alone():
    result = normalise_set([row(collector_number=""), row()], set_code="FE01")
    assert len(result.cards) == 1
    assert result.rejections[0].reason_code == "missing_required_field"
    assert result.rejections[0].field == "collector_number"


def test_missing_name_is_rejected():
    rejection = only_rejection(normalise_set([row(name="")], set_code="FE01"))
    assert rejection.reason_code == "missing_required_field"
    assert rejection.field == "name"


def test_elestral_without_element_is_a_type_mismatch():
    rejection = only_rejection(normalise_set([row(element="")], set_code="FE01"))
    assert rejection.reason_code == "type_field_mismatch"
    assert rejection.field == "element"


def test_rune_with_attack_is_a_type_mismatch():
    rejection = only_rejection(normalise_set(
        [row(card_type="rune", rune_type="invoke", element="", attack="100", defence="")],
        set_code="FE01",
    ))
    assert rejection.reason_code == "type_field_mismatch"


def test_rune_without_rune_type_is_a_type_mismatch():
    rejection = only_rejection(normalise_set(
        [row(card_type="rune", rune_type="", element="", attack="", defence="")],
        set_code="FE01",
    ))
    assert rejection.reason_code == "type_field_mismatch"
    assert rejection.field == "rune_type"


def test_valid_rune_normalises():
    result = normalise_set(
        [row(card_type="rune", rune_type="invoke", element="", attack="", defence="",
             spirit_cost="")],
        set_code="FE01",
    )
    assert not result.rejections
    (card,) = result.cards
    assert card.card_type == "rune" and card.rune_type == "invoke"
    assert card.attack is None and card.spirit_cost is None


def test_malformed_spirit_cost_is_rejected():
    rejection = only_rejection(normalise_set([row(spirit_cost="2 earth")], set_code="FE01"))
    assert rejection.reason_code == "invalid_spirit_cost"


def test_spirit_cost_with_unknown_element_is_rejected():
    rejection = only_rejection(normalise_set(
        [row(spirit_cost='{"plasma": 2}')], set_code="FE01"
    ))
    assert rejection.reason_code == "invalid_spirit_cost"


def test_negative_spirit_cost_is_rejected():
    rejection = only_rejection(normalise_set(
        [row(spirit_cost='{"earth": -1}')], set_code="FE01"
    ))
    assert rejection.reason_code == "invalid_spirit_cost"


def test_non_integer_attack_is_rejected():
    rejection = only_rejection(normalise_set([row(attack="lots")], set_code="FE01"))
    assert rejection.reason_code == "type_field_mismatch"
    assert rejection.field == "attack"


def test_normaliser_never_raises_on_garbage():
    """Totality: an exception mid-run would take a whole import down over one bad row."""
    garbage = RawRecord(source_ref="x:1", data={"collector_number": "\x00", "name": "?"})
    result = normalise_set([garbage], set_code="FE01")
    assert result.rejections and not result.cards


def test_rejection_carries_the_raw_record_for_the_operator():
    rejection = only_rejection(normalise_set([row(rarity="nope")], set_code="FE01"))
    assert rejection.raw_record["name"] == "Teratlas"
    assert rejection.source_ref == "FE01.csv:2"
