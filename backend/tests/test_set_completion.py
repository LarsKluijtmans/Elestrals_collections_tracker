"""Set completion — the projection that must never disagree with its source."""
from __future__ import annotations

import pytest

from app.repositories.set_completion_repository import SetCompletionRepository
from app.repositories.set_repository import SetRepository
from app.services.completion_service import CompletionService
from test_inventory import ALICE, BOB, build_service, seed_catalog


@pytest.fixture()
def catalog(db):
    return seed_catalog(db, card_count=3)


@pytest.fixture()
def svc(db):
    return build_service(db)


@pytest.fixture()
def completion(db):
    return CompletionService(SetCompletionRepository(db), SetRepository(db))


def view_for(completion, user=ALICE):
    views = completion.view(user)
    return views[0] if views else None


def test_completion_is_correct_immediately_after_a_write(svc, completion, catalog):
    """No refresh, no eventual consistency. A collector who adds a card and sees the old
    number stops trusting every number on the page."""
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])

    row = view_for(completion)
    assert row.owned_cards == 1
    assert row.card_count == 3
    assert row.total_quantity == 1
    assert row.ratio == pytest.approx(1 / 3)


def test_two_printings_of_one_card_count_as_one_card(svc, completion, catalog):
    """Completion counts distinct cards, not printings — 126 cards can carry 189 printings,
    and the wrong denominator reads above 100%."""
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:holo_rare"])

    row = view_for(completion)
    assert row.owned_cards == 1
    assert row.total_quantity == 2


def test_quantity_does_not_inflate_owned_cards(svc, completion, catalog):
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"], quantity=9)
    row = view_for(completion)
    assert row.owned_cards == 1
    assert row.total_quantity == 9


def test_completion_tracks_a_full_set(svc, completion, catalog):
    for n in (1, 2, 3):
        svc.add(ALICE, printing_id=catalog["printings"][f"BS1-{n:03d}:common"])
    row = view_for(completion)
    assert (row.owned_cards, row.card_count) == (3, 3)
    assert row.ratio == 1.0


def test_removing_the_last_copy_lowers_completion(svc, completion, catalog):
    item = svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"]).item
    assert view_for(completion).owned_cards == 1

    svc.remove(ALICE, item.id)
    assert view_for(completion).owned_cards == 0


def test_editing_quantity_updates_the_copy_count(svc, completion, catalog):
    from app.services.inventory_service import ItemFields

    item = svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"]).item
    svc.edit(ALICE, item.id, ItemFields(quantity=4))

    row = view_for(completion)
    assert row.owned_cards == 1
    assert row.total_quantity == 4


def test_completion_is_per_user(svc, completion, catalog):
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    svc.add(BOB, printing_id=catalog["printings"]["BS1-002:common"])
    svc.add(BOB, printing_id=catalog["printings"]["BS1-003:common"])

    assert view_for(completion, ALICE).owned_cards == 1
    assert view_for(completion, BOB).owned_cards == 2


def test_rebuild_regenerates_the_whole_projection(svc, completion, catalog, db):
    """The repair path: if the projection is ever wrong, this reconstructs it from the only
    source of truth there is."""
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])

    # Corrupt it the way a bad migration or a bug would.
    row = SetCompletionRepository(db).get(ALICE, catalog["set"].id)
    row.owned_cards = 99
    db.commit()
    assert view_for(completion).owned_cards == 99

    completion.rebuild_for_user(ALICE)
    db.commit()

    assert view_for(completion).owned_cards == 1


def test_rebuild_covers_sets_the_user_owns_nothing_from(completion, catalog, db):
    completion.rebuild_for_user(ALICE)
    db.commit()

    row = view_for(completion)
    assert row is not None
    assert (row.owned_cards, row.card_count) == (0, 3)


def test_ratio_is_guarded_against_an_undeclared_set(svc, completion, catalog, db):
    """A set with no declared printed size has no meaningful percentage, and x/0 is not a
    number a UI can render."""
    catalog["set"].card_count = 0
    db.commit()

    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    assert view_for(completion).ratio == 0.0
