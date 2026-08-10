"""Two small pure modules that several screens depend on agreeing about."""
from __future__ import annotations

from dataclasses import dataclass

from app.services.alt_text import alt_for_card, alt_for_printing
from app.services.rarity_order import RARITY_ORDER, primary_printing, rarity_rank


@dataclass
class P:
    id: str
    rarity: str
    finish: str = "normal"
    edition: str = "first"


def test_rarity_order_is_commonest_first():
    ranks = [rarity_rank(r) for r in RARITY_ORDER]
    assert ranks == sorted(ranks)
    assert rarity_rank("common") < rarity_rank("holo_rare") < rarity_rank("secret")


def test_unknown_rarity_sorts_last_without_raising():
    """Ranking is a display concern and must not be able to break a page."""
    assert rarity_rank("mythic") == len(RARITY_ORDER)


def test_primary_printing_is_the_commonest():
    printings = [P("a", "holo_rare"), P("b", "common"), P("c", "rare")]
    assert primary_printing(printings).id == "b"


def test_primary_printing_falls_back_to_whatever_exists():
    """A card whose only printing is `secret` still needs to show one."""
    assert primary_printing([P("only", "secret")]).id == "only"


def test_primary_printing_is_deterministic_under_ties():
    a = [P("z", "rare"), P("a", "rare")]
    b = [P("a", "rare"), P("z", "rare")]
    assert primary_printing(a).id == primary_printing(b).id == "a"


def test_no_printings_yields_none():
    assert primary_printing([]) is None


def test_alt_text_uses_an_em_dash_and_the_specified_shape():
    assert alt_for_printing(name="Teratlas", set_code="FE01", rarity="rare") == (
        "Teratlas — FE01 rare"
    )


def test_alt_text_degrades_without_a_rarity():
    """A card with no printings is a catalog defect, but a page must still render."""
    assert alt_for_card(name="Teratlas", set_code="FE01", rarity=None) == "Teratlas — FE01"
