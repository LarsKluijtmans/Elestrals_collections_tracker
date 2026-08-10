"""Search ranking — the tiers, and the total order bolt 005 will commit against."""
from __future__ import annotations

import pytest

from app.importer.canonical import CanonicalCard, CanonicalPrinting
from app.models.set import Set
from app.repositories.card_repository import CardRepository, SearchQuery
from app.repositories.printing_repository import PrintingRepository
from app.services.catalog_read_service import CardSearchService
from app.services.catalog_upsert import CatalogUpsert


def add_card(db, set_row, number, name, *, card_type="elestral", element="fire",
             rarities=("rare",)):
    CatalogUpsert(CardRepository(db)).upsert(
        CanonicalCard(
            set_code=set_row.code, collector_number=number, name=name,
            card_type=card_type,
            element=element if card_type != "rune" else None,
            rune_type="invoke" if card_type == "rune" else None,
            printings=tuple(
                CanonicalPrinting(rarity=r, finish="normal", language="en", edition="first")
                for r in rarities
            ),
        ),
        set_id=set_row.id,
    )


@pytest.fixture()
def catalog(db):
    base = Set(code="FE01", name="Base", card_count=10, released_on=None)
    later = Set(code="DC01", name="Firestorm", card_count=10)
    db.add_all([base, later])
    db.commit()

    add_card(db, base, "BS1-001", "Atlas")                      # exact for "atlas"
    add_card(db, base, "BS1-002", "Atlasborn")                  # name prefix
    add_card(db, base, "BS1-003", "Great Atlas Wyrm")           # word prefix
    add_card(db, base, "BS1-004", "Teratlas")                   # infix
    add_card(db, base, "BS1-005", "Unrelated", element="water")
    add_card(db, later, "DC1-001", "Atlas Echo", rarities=("holo_rare",))
    return {"base": base, "later": later}


@pytest.fixture()
def search(db):
    svc = CardSearchService(CardRepository(db), PrintingRepository(db))
    return lambda **kw: svc.search(SearchQuery(**kw))


def names(items):
    return [i.name for i in items]


def test_tiers_rank_in_order(search, catalog):
    items, _ = search(term="atlas", limit=50)
    kinds = [i.match_kind for i in items]

    assert kinds[0] == "exact_name"
    assert items[0].name == "Atlas"
    # Each tier appears no earlier than the one before it.
    order = ["exact_name", "name_prefix", "word_prefix", "collector_number", "set_code", "infix"]
    positions = [order.index(k) for k in kinds]
    assert positions == sorted(positions), kinds


def test_infix_match_is_found_and_ranked_last(search, catalog):
    """The 'Teratlas' case — the thing the Stage 1 example got wrong."""
    items, _ = search(term="atlas", limit=50)
    assert "Teratlas" in names(items)
    assert items[names(items).index("Teratlas")].match_kind == "infix"


def test_word_prefix_matches_a_word_inside_the_name(search, catalog):
    items, _ = search(term="atlas", limit=50)
    entry = next(i for i in items if i.name == "Great Atlas Wyrm")
    assert entry.match_kind == "word_prefix"


def test_collector_number_is_searchable(search, catalog):
    items, _ = search(term="BS1-003", limit=50)
    assert names(items) == ["Great Atlas Wyrm"]
    assert items[0].match_kind == "collector_number"


def test_set_code_returns_the_whole_set(search, catalog):
    items, _ = search(term="DC01", limit=50)
    assert names(items) == ["Atlas Echo"]
    assert items[0].match_kind == "set_code"


def test_order_is_stable_across_identical_queries(search, catalog):
    """If this wobbles, bolt 005's Enter-to-add commits the wrong printing silently."""
    first, _ = search(term="atlas", limit=50)
    second, _ = search(term="atlas", limit=50)
    assert [i.card_id for i in first] == [i.card_id for i in second]


def test_short_terms_return_nothing_without_querying(search, catalog):
    items, total = search(term="a", limit=50)
    assert items == [] and total == 0


def test_wildcards_in_a_term_are_literal(search, catalog):
    """A search for `%` must not match everything."""
    items, total = search(term="%%", limit=50)
    assert items == [] and total == 0


def test_underscore_is_literal_too(search, catalog):
    items, _ = search(term="atl_s", limit=50)
    assert items == []


def test_element_filter_narrows(search, catalog):
    items, _ = search(term="atlas", elements=["water"], limit=50)
    assert items == []

    items, _ = search(term="atlas", elements=["fire"], limit=50)
    assert names(items)


def test_set_filter_narrows(search, catalog):
    items, _ = search(term="atlas", set_codes=["DC01"], limit=50)
    assert names(items) == ["Atlas Echo"]


def test_rarity_filter_matches_on_any_printing(search, catalog):
    items, _ = search(term="atlas", rarities=["holo_rare"], limit=50)
    assert names(items) == ["Atlas Echo"]


def test_card_type_filter(db, search, catalog):
    add_card(db, catalog["base"], "BS1-006", "Atlas Rune", card_type="rune")
    items, _ = search(term="atlas", card_types=["rune"], limit=50)
    assert names(items) == ["Atlas Rune"]


def test_paging_does_not_skip_or_repeat(search, catalog):
    page1, total = search(term="atlas", limit=2, offset=0)
    page2, _ = search(term="atlas", limit=2, offset=2)

    ids = [i.card_id for i in page1] + [i.card_id for i in page2]
    assert len(ids) == len(set(ids)), "a row appeared on two pages"
    assert total >= len(ids)


def test_result_carries_a_primary_printing_and_count(db, catalog, search):
    add_card(db, catalog["base"], "BS1-007", "Atlas Twin",
             rarities=("holo_rare", "common", "rare"))
    entry = next(i for i in search(term="Atlas Twin", limit=10)[0] if i.name == "Atlas Twin")

    assert entry.printing_count == 3
    # Commonest first, so the row reads as the version a collector pictures.
    assert entry.primary_printing.rarity == "common"
    assert entry.primary_printing.alt_text == "Atlas Twin — FE01 common"


def test_search_is_case_insensitive(search, catalog):
    assert names(search(term="ATLAS", limit=50)[0])
