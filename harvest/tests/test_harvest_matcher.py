"""Title → SKU, and — more often — title → refusal.

The interesting half of these tests is the rejections. A matcher that places 95% of titles is
worse than one that places 60%, if the extra 35% are wrong: an observation carries a price
into a median that a collection valuation is computed from, and a wrong SKU there is invisible
forever after. So each guard gets its own test with the failure it prevents written down.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.harvest.catalog_index import CatalogIndex, PrintingEntry, SealedEntry, SetEntry
from app.harvest.matcher import TitleMatcher

FLOOR = Decimal("0.70")


def printing(printing_id, name, set_code, number, rarity, finish, language="en",
             edition="first") -> PrintingEntry:
    return PrintingEntry(
        printing_id=printing_id, card_id=f"card-{name}", card_name=name, set_code=set_code,
        set_name="Base Set" if set_code == "FE01" else "Moonrise", collector_number=number,
        rarity=rarity, finish=finish, language=language, edition=edition,
    )


@pytest.fixture()
def index() -> CatalogIndex:
    return CatalogIndex(
        printings=[
            printing("p-normal", "Vipyro", "FE01", "012", "rare", "normal"),
            printing("p-foil", "Vipyro", "FE01", "012", "holo_rare", "foil"),
            printing("p-ja", "Vipyro", "FE01", "012", "rare", "normal", language="ja"),
            printing("p-aquagon", "Aquagon", "FE01", "045", "common", "normal"),
            printing("p-ascended", "Vipyro Ascended", "FE02", "007", "rare", "normal",
                     edition="unlimited"),
        ],
        sealed=[
            SealedEntry(sealed_product_id="s-box", name="Base Set Booster Box",
                        kind="booster_box", set_code="FE01"),
        ],
        sets=[SetEntry(code="FE01", name="Base Set"), SetEntry(code="FE02", name="Moonrise")],
    )


@pytest.fixture()
def matcher(index) -> TitleMatcher:
    return TitleMatcher(index, floor=FLOOR)


# --- what should match ---------------------------------------------------------------

def test_a_fully_specified_title_matches_one_printing(matcher):
    match = matcher.match("Elestrals Vipyro FE01 012/126 Holo 1st Edition NM")

    assert match.printing_id == "p-foil"
    assert match.condition == "near_mint"
    assert match.clears(FLOOR)


def test_the_longer_card_name_wins_over_the_shorter_one_inside_it(matcher):
    """"Vipyro Ascended" contains "Vipyro". Matching the shorter name first would price a
    different card, and counting both would report an ambiguity that is not there."""
    match = matcher.match("Elestrals Vipyro Ascended FE02 007/090")

    assert match.printing_id == "p-ascended"
    assert match.clears(FLOOR)


def test_a_japanese_title_matches_the_japanese_printing(matcher):
    match = matcher.match("Elestrals Vipyro FE01 012/126 Japanese")

    assert match.printing_id == "p-ja"


def test_a_sealed_product_matches_by_name(matcher):
    match = matcher.match("Elestrals Base Set Booster Box Factory Sealed")

    assert match.sealed_product_id == "s-box"
    assert match.kind == "sealed"
    assert match.clears(FLOOR)


# --- what should be refused ----------------------------------------------------------

def test_a_graded_slab_is_refused(matcher):
    """A PSA 10 and a raw copy are two markets. The schema has nowhere to put the grade, so a
    slab price in a raw median would silently inflate every valuation containing that card."""
    match = matcher.match("Elestrals Vipyro FE01 012/126 PSA 10 GEM MINT")

    assert not match.clears(FLOOR)
    assert "graded" in match.note


def test_a_multi_card_lot_is_refused(matcher):
    """"3x Vipyro" at $30 is not a $30 Vipyro, and dividing by a quantity parsed out of a
    title is arithmetic on a guess."""
    match = matcher.match("Elestrals Vipyro FE01 3x Playset NM")

    assert match.kind == "lot"
    assert not match.clears(FLOOR)


def test_a_proxy_is_refused(matcher):
    match = matcher.match("Elestrals Vipyro FE01 012/126 Custom Proxy Card")

    assert not match.clears(FLOOR)
    assert "proxy" in match.note


def test_a_language_with_no_printing_is_refused_rather_than_folded_onto_english(matcher):
    """The failure this prevents: recording a Japanese card's price against the English
    printing, which is not a cheaper version of it but a different card."""
    match = matcher.match("Elestrals Aquagon FE01 045/126 Japanese")

    assert match.printing_id is None
    assert "no ja printing" in match.note


def test_an_underspecified_title_falls_under_the_floor(matcher):
    """Two printings survive and nothing in the title chooses between them. The match is a
    guess, so it is counted as rejected — FR-3: not stored as a low-confidence fact."""
    match = matcher.match("Elestrals Vipyro card")

    assert not match.clears(FLOOR)
    assert "printings matched" in match.note


def test_two_card_names_in_one_title_cost_confidence(matcher):
    single = matcher.match("Elestrals Vipyro FE01 012/126 Holo 1st Edition")
    ambiguous = matcher.match("Elestrals Vipyro Aquagon FE01 012/126 Holo 1st Edition")

    assert ambiguous.confidence < single.confidence
    assert "ambiguous" in ambiguous.note


def test_a_title_with_no_catalog_name_matches_nothing(matcher):
    match = matcher.match("Pokemon Charizard Base Set Holo")

    assert match.kind == "unknown"
    assert match.confidence == Decimal("0")


# --- leads, not matches ---------------------------------------------------------------

def test_an_unknown_sealed_product_is_kept_as_a_lead(matcher):
    """Confidence 0, so no price is recorded — but the note says what it is, because a sealed
    product missing from the catalog is exactly what a deep scan is for."""
    match = matcher.match("Elestrals Shadow Realm Booster Box Sealed")

    assert match.kind == "sealed"
    assert not match.clears(FLOOR)
    assert "candidate for the sealed catalog" in match.note
