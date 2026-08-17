"""Browsing the collection — stories 019, 020, 024.

The assertion this file exists for is `test_a_row_inserted_while_paging_does_not_shift_the_page`.
Every other test here passes against an offset cursor too. Offsets fail exactly where this product
lives — a collector adds cards *while* scrolling — and they fail silently: page 2 repeats a row or
skips one, and neither looks like an error. It looks like the table lost a card, which is the worst
thing this product can do.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.pagination import decode_keyset, encode_keyset
from app.repositories.card_repository import CardRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.set_repository import SetRepository
from app.services.collection_browse_service import CollectionBrowseService
from app.services.collection_filters import FilterSet, InvalidFilter
from test_inventory import ALICE, BOB, build_service, seed_catalog


@pytest.fixture()
def catalog(db):
    return seed_catalog(db, card_count=6)


@pytest.fixture()
def svc(db):
    return build_service(db)


@pytest.fixture()
def browse(db):
    return CollectionBrowseService(
        InventoryRepository(db), CardRepository(db), SetRepository(db)
    )


def no_filters() -> FilterSet:
    return FilterSet.from_params({})


def stagger(db, items, *, seconds=60):
    """Give rows distinct `created_at` values.

    Seeded rows otherwise share a timestamp to the microsecond, which would let the `id`
    tie-break carry the whole ordering and hide a broken keyset predicate.
    """
    base = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    for n, item in enumerate(items):
        item.created_at = base + timedelta(seconds=n * seconds)
    db.commit()
    return items


def add_many(svc, catalog, db, count: int, *, user=ALICE):
    items = [
        svc.add(user, printing_id=catalog["printings"][f"BS1-{n:03d}:common"]).item
        for n in range(1, count + 1)
    ]
    return stagger(db, items)


# --- the page ------------------------------------------------------------------------

def test_an_empty_collection_is_a_page_of_nothing_not_an_error(browse):
    page = browse.page(ALICE, no_filters())
    assert page.items == []
    assert page.total == 0
    assert page.next_cursor is None


def test_newest_first_by_default(browse, svc, catalog, db):
    """The fast-add flow makes this true rather than merely plausible: the last thing you added
    is the thing you are most likely looking for."""
    items = add_many(svc, catalog, db, 3)
    page = browse.page(ALICE, no_filters())
    assert [i.id for i in page.items] == [items[2].id, items[1].id, items[0].id]


def test_the_total_counts_matches_not_the_page(browse, svc, catalog, db):
    """"Showing 2 of 2" when there are six is how a collector comes to believe they have lost
    cards. The count is its own query for exactly this reason."""
    add_many(svc, catalog, db, 6)
    page = browse.page(ALICE, no_filters(), limit=2)
    assert len(page.items) == 2
    assert page.total == 6


def test_another_users_rows_are_not_in_the_page(browse, svc, catalog, db):
    add_many(svc, catalog, db, 3)
    add_many(svc, catalog, db, 2, user=BOB)

    assert browse.page(ALICE, no_filters()).total == 3
    assert browse.page(BOB, no_filters()).total == 2


def test_an_unknown_sort_is_refused(browse):
    with pytest.raises(InvalidFilter):
        browse.page(ALICE, no_filters(), sort="by_vibes")


# --- keyset paging -------------------------------------------------------------------

def test_paging_walks_every_row_exactly_once(browse, svc, catalog, db):
    items = add_many(svc, catalog, db, 6)

    seen, cursor = [], None
    while True:
        page = browse.page(ALICE, no_filters(), limit=2, cursor=cursor)
        seen.extend(i.id for i in page.items)
        cursor = page.next_cursor
        if cursor is None:
            break

    assert seen == [i.id for i in reversed(items)]
    assert len(set(seen)) == 6


def test_the_last_page_has_no_cursor(browse, svc, catalog, db):
    """A cursor on the final page makes a client fetch an empty page to discover it is done —
    one wasted round trip on every single scroll to the bottom."""
    add_many(svc, catalog, db, 4)
    page = browse.page(ALICE, no_filters(), limit=4)
    assert len(page.items) == 4
    assert page.next_cursor is None


def test_a_row_inserted_while_paging_does_not_shift_the_page(browse, svc, catalog, db):
    """**The reason this is keyset and not offset.**

    A collector pages to row 2, then adds a card — which lands at the top of a newest-first sort.
    With `OFFSET 2` the window slides down by one and the third row is returned twice. Nothing
    errors. The table just quietly repeats a card and hides another.
    """
    items = add_many(svc, catalog, db, 4)
    first = browse.page(ALICE, no_filters(), limit=2)
    assert [i.id for i in first.items] == [items[3].id, items[2].id]

    newcomer = svc.add(ALICE, printing_id=catalog["printings"]["BS1-005:common"]).item
    stagger(db, [*items, newcomer], seconds=60)

    second = browse.page(ALICE, no_filters(), limit=2, cursor=first.next_cursor)

    assert [i.id for i in second.items] == [items[1].id, items[0].id]
    assert newcomer.id not in {i.id for i in second.items}


def test_a_row_deleted_while_paging_does_not_skip_one(browse, svc, catalog, db):
    """The mirror image, and the more dangerous one: an offset moves *up*, so page 2 skips a row
    entirely and the collector never sees it."""
    items = add_many(svc, catalog, db, 5)
    first = browse.page(ALICE, no_filters(), limit=2)

    svc.remove(ALICE, items[4].id)

    second = browse.page(ALICE, no_filters(), limit=2, cursor=first.next_cursor)
    assert [i.id for i in second.items] == [items[2].id, items[1].id]


def test_rows_sharing_a_timestamp_still_page_totally(browse, svc, catalog, db):
    """Without the `id` tie-break the order is not total, and two rows created in the same
    millisecond can straddle a page boundary — one of them is then never returned at all."""
    items = [
        svc.add(ALICE, printing_id=catalog["printings"][f"BS1-{n:03d}:common"]).item
        for n in range(1, 5)
    ]
    same = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    for item in items:
        item.created_at = same
    db.commit()

    seen, cursor = [], None
    for _ in range(10):
        page = browse.page(ALICE, no_filters(), limit=2, cursor=cursor)
        seen.extend(i.id for i in page.items)
        cursor = page.next_cursor
        if cursor is None:
            break

    assert sorted(seen) == sorted(i.id for i in items)
    assert len(seen) == len(set(seen))


def test_a_malformed_cursor_is_loud(browse):
    with pytest.raises(ValueError):
        browse.page(ALICE, no_filters(), cursor="not-base64!!")


def test_a_cursor_from_a_different_sort_is_refused(browse, svc, catalog, db):
    """A stale cursor must fail rather than be unpacked into the wrong column and silently return
    an arbitrary page that the client believes is the next one."""
    add_many(svc, catalog, db, 3)
    quantity_cursor = encode_keyset("3", "some-id")

    with pytest.raises(ValueError):
        browse.page(ALICE, no_filters(), sort="added_desc", cursor=quantity_cursor)


def test_a_cursor_with_the_wrong_number_of_parts_is_refused():
    with pytest.raises(ValueError):
        decode_keyset(encode_keyset("only-one"), arity=2)


# --- sorting -------------------------------------------------------------------------

def test_sorting_by_quantity(browse, svc, catalog, db):
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"], quantity=5)
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-002:common"], quantity=1)
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-003:common"], quantity=3)

    page = browse.page(ALICE, no_filters(), sort="quantity_desc")
    assert [i.quantity for i in page.items] == [5, 3, 1]


def test_sorting_by_name_joins_the_catalog_even_with_no_filters(browse, svc, catalog, db):
    """The join is conditional on the filters *and* the sort. Forgetting the second half is a
    missing-FROM error at request time rather than at import."""
    add_many(svc, catalog, db, 3)
    page = browse.page(ALICE, no_filters(), sort="name_asc")
    assert len(page.items) == 3


def test_quantity_paging_walks_every_row(browse, svc, catalog, db):
    for n, qty in enumerate([5, 1, 3, 2], start=1):
        svc.add(ALICE, printing_id=catalog["printings"][f"BS1-{n:03d}:common"], quantity=qty)

    seen, cursor = [], None
    for _ in range(10):
        page = browse.page(ALICE, no_filters(), sort="quantity_desc", limit=2, cursor=cursor)
        seen.extend(i.quantity for i in page.items)
        cursor = page.next_cursor
        if cursor is None:
            break

    assert seen == [5, 3, 2, 1]


# --- filters -------------------------------------------------------------------------

def test_filtering_by_condition(browse, svc, catalog, db):
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"], condition="near_mint")
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-002:common"], condition="damaged")

    page = browse.page(ALICE, FilterSet.from_params({"condition": ["damaged"]}))
    assert page.total == 1
    assert page.items[0].condition == "damaged"


def test_filters_or_within_an_attribute(browse, svc, catalog, db):
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"], condition="near_mint")
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-002:common"], condition="damaged")
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-003:common"], condition="mint")

    page = browse.page(ALICE, FilterSet.from_params({"condition": ["damaged", "mint"]}))
    assert page.total == 2


def test_filters_and_across_attributes(browse, svc, catalog, db):
    """Story 020's combining rule, in one assertion: `(rarity=common) AND (condition=damaged)`."""
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"], condition="damaged")
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-002:holo_rare"], condition="damaged")
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-003:common"], condition="mint")

    page = browse.page(ALICE, FilterSet.from_params({
        "rarity": ["common"], "condition": ["damaged"],
    }))
    assert page.total == 1


def test_filtering_by_rarity_and_finish(browse, svc, catalog, db):
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:holo_rare"])

    assert browse.page(ALICE, FilterSet.from_params({"finish": ["foil"]})).total == 1
    assert browse.page(ALICE, FilterSet.from_params({"rarity": ["holo_rare"]})).total == 1


def test_filtering_by_set_code(browse, svc, catalog, db):
    add_many(svc, catalog, db, 3)
    assert browse.page(ALICE, FilterSet.from_params({"set_code": ["FE01"]})).total == 3
    assert browse.page(ALICE, FilterSet.from_params({"set_code": ["NOPE"]})).total == 0


def test_filtering_on_a_set_you_own_nothing_from_is_allowed_and_empty(browse, svc, catalog, db):
    add_many(svc, catalog, db, 2)
    page = browse.page(ALICE, FilterSet.from_params({"set_code": ["FE99"]}))
    assert page.items == []
    assert page.total == 0


def test_filtering_by_graded(browse, svc, catalog, db):
    pid = catalog["printings"]["BS1-001:common"]
    svc.add(ALICE, printing_id=pid)
    svc.add(ALICE, printing_id=pid, is_graded=True, grader="PSA", grade=9)

    assert browse.page(ALICE, FilterSet.from_params({"is_graded": "true"})).total == 1
    assert browse.page(ALICE, FilterSet.from_params({"is_graded": "false"})).total == 1
    # Absent means "either", not "false".
    assert browse.page(ALICE, no_filters()).total == 2


def test_searching_by_name(browse, svc, catalog, db):
    add_many(svc, catalog, db, 3)
    assert browse.page(ALICE, FilterSet.from_params({"q": "Card 2"})).total == 1
    assert browse.page(ALICE, FilterSet.from_params({"q": "Card"})).total == 3


def test_a_wildcard_in_the_search_term_is_a_literal(browse, svc, catalog, db):
    """`%` typed by a user is a character, not an instruction. Without escaping, searching `%`
    matches everything — which looks like the filter being ignored."""
    add_many(svc, catalog, db, 3)
    assert browse.page(ALICE, FilterSet.from_params({"q": "%"})).total == 0


def test_paging_a_filtered_set_stays_filtered(browse, svc, catalog, db):
    for n in range(1, 5):
        svc.add(ALICE, printing_id=catalog["printings"][f"BS1-{n:03d}:common"],
                condition="damaged" if n % 2 else "near_mint")
    stagger(db, InventoryRepository(db).list_for_user(ALICE))

    first = browse.page(ALICE, FilterSet.from_params({"condition": ["damaged"]}), limit=1)
    second = browse.page(
        ALICE, FilterSet.from_params({"condition": ["damaged"]}),
        limit=1, cursor=first.next_cursor,
    )
    assert all(i.condition == "damaged" for i in [*first.items, *second.items])
    assert first.total == 2


# --- missing cards (story 024) -------------------------------------------------------

def test_missing_lists_cards_with_no_owned_printing(browse, svc, catalog):
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])

    report = browse.missing_from_set(ALICE, "FE01")
    assert report.owned_cards == 1
    assert "BS1-001" not in [c.collector_number for c in report.missing]
    assert len(report.missing) == 5


def test_owning_any_printing_means_the_card_is_not_missing(browse, svc, catalog):
    """**The definition that matters.** Missing is per card, not per printing — owning the common
    version means you have the card, even without the holo. The other reading makes a completed
    set permanently incomplete and puts this view at odds with the completion ring."""
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:holo_rare"])

    report = browse.missing_from_set(ALICE, "FE01")
    assert "BS1-001" not in [c.collector_number for c in report.missing]


def test_missing_counts_against_the_declared_printed_size(browse, svc, catalog):
    """`card_count` is what the set says it printed, not what our catalog imported — so this
    figure and the dashboard ring are computed from the same denominator and cannot disagree."""
    report = browse.missing_from_set(ALICE, "FE01")
    assert report.card_count == 6
    assert report.owned_cards == 0


def test_missing_from_an_unknown_set_is_none(browse):
    assert browse.missing_from_set(ALICE, "NOPE") is None


def test_missing_is_owner_scoped(browse, svc, catalog):
    svc.add(BOB, printing_id=catalog["printings"]["BS1-001:common"])
    report = browse.missing_from_set(ALICE, "FE01")
    assert report.owned_cards == 0
    assert len(report.missing) == 6
