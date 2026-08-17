"""Bulk edit and delete — story 022.

Two properties, and the story states both as requirements rather than preferences:

* **A selection is a filter.** Select-all over 10,000 rows must not put 10,000 ids on the wire.
* **Partial success is reported honestly.** One row that moved must not fail the other 499, and it
  must not be swallowed either — the report names it.

The second is why this is not one transaction, which is a deliberate trade: the report is what
makes a bulk operation safe here, not the rollback.
"""
from __future__ import annotations

import pytest

from app.repositories.inventory_repository import InventoryRepository
from app.services.bulk_service import MAX_SELECTION, BulkService, SelectionTooLarge
from app.services.collection_filters import FilterSet
from app.services.inventory_service import ItemFields
from test_inventory import ALICE, BOB, build_service, seed_catalog


@pytest.fixture()
def catalog(db):
    return seed_catalog(db, card_count=6)


@pytest.fixture()
def svc(db):
    return build_service(db)


@pytest.fixture()
def bulk(db, svc):
    return BulkService(InventoryRepository(db), svc)


def add_range(svc, catalog, count, *, user=ALICE, condition="near_mint"):
    return [
        svc.add(user, printing_id=catalog["printings"][f"BS1-{n:03d}:common"],
                condition=condition).item
        for n in range(1, count + 1)
    ]


# --- resolving a selection -----------------------------------------------------------

def test_explicit_ids_resolve_to_themselves(bulk, svc, catalog):
    items = add_range(svc, catalog, 3)
    ids = bulk.resolve(ALICE, item_ids=[i.id for i in items], filters=None)
    assert ids == [i.id for i in items]


def test_duplicate_ids_collapse(bulk, svc, catalog):
    item = add_range(svc, catalog, 1)[0]
    assert bulk.resolve(ALICE, item_ids=[item.id, item.id], filters=None) == [item.id]


def test_a_filter_resolves_to_the_rows_it_matches(bulk, svc, catalog):
    """Select-all is the filter, not 10,000 ids. This is where it becomes rows — once,
    server-side, where the filter already lives."""
    add_range(svc, catalog, 3, condition="damaged")
    add_range(svc, catalog, 0)

    ids = bulk.resolve(ALICE, item_ids=None, filters=FilterSet.from_params(
        {"condition": ["damaged"]}
    ))
    assert len(ids) == 3


def test_a_filter_only_resolves_the_callers_own_rows(bulk, svc, catalog):
    add_range(svc, catalog, 2, user=BOB)
    assert bulk.resolve(ALICE, item_ids=None, filters=FilterSet.from_params({})) == []


def test_no_selection_at_all_is_empty(bulk):
    assert bulk.resolve(ALICE, item_ids=None, filters=None) == []


def test_an_oversized_id_list_is_refused(bulk):
    with pytest.raises(SelectionTooLarge):
        bulk.resolve(ALICE, item_ids=[f"id-{n}" for n in range(MAX_SELECTION + 1)], filters=None)


def test_an_oversized_filter_is_refused_rather_than_truncated(bulk, monkeypatch, db):
    """**Truncating would be the worst outcome available**: apply the operation to an arbitrary
    5,000 of a larger selection and report success. So the cap is fetched with one row of
    headroom, purely so the overflow can be detected."""
    monkeypatch.setattr(
        InventoryRepository, "ids_matching",
        lambda self, user, filters, *, cap: [f"id-{n}" for n in range(cap)],
    )
    with pytest.raises(SelectionTooLarge):
        bulk.resolve(ALICE, item_ids=None, filters=FilterSet.from_params({}))


# --- bulk edit -----------------------------------------------------------------------

def test_editing_applies_to_every_row(bulk, svc, catalog, db):
    items = add_range(svc, catalog, 3)
    result = bulk.edit(ALICE, [i.id for i in items],
                       ItemFields(storage_location="binder 2", is_for_trade=True))

    assert result.requested == 3
    assert result.applied == 3
    assert result.failures == []
    assert result.partial is False

    for item in InventoryRepository(db).list_for_user(ALICE):
        assert item.storage_location == "binder 2"
        assert item.is_for_trade is True


def test_a_row_that_vanished_fails_alone_and_is_named(bulk, svc, catalog, db):
    """Story 022's edge case: a row deleted in another tab between selection and action. That row
    fails, it is named, and the others still apply."""
    items = add_range(svc, catalog, 3)
    svc.remove(ALICE, items[1].id)

    result = bulk.edit(ALICE, [i.id for i in items], ItemFields(is_for_trade=True))

    assert result.applied == 2
    assert result.partial is True
    assert [f.item_id for f in result.failures] == [items[1].id]
    assert result.failures[0].code == "inventory_item_not_found"


def test_another_users_row_fails_as_not_found_not_forbidden(bulk, svc, catalog):
    """A 403 here would confirm the id exists. Same rule as everywhere else a user owns rows."""
    mine = add_range(svc, catalog, 1)[0]
    theirs = svc.add(BOB, printing_id=catalog["printings"]["BS1-002:common"]).item

    result = bulk.edit(ALICE, [mine.id, theirs.id], ItemFields(is_for_trade=True))

    assert result.applied == 1
    assert result.failures[0].code == "inventory_item_not_found"


def test_another_users_row_is_not_modified(bulk, svc, catalog, db):
    theirs = svc.add(BOB, printing_id=catalog["printings"]["BS1-002:common"],
                     storage_location="their binder").item

    bulk.edit(ALICE, [theirs.id], ItemFields(storage_location="mine now"))

    assert InventoryRepository(db).get(BOB, theirs.id).storage_location == "their binder"


def test_an_invalid_value_fails_that_row_only(bulk, svc, catalog):
    items = add_range(svc, catalog, 2)
    result = bulk.edit(ALICE, [i.id for i in items], ItemFields(condition="not_a_condition"))

    # Every row rejects the same bad value, so nothing applies — but each failure is still named
    # individually rather than collapsing into one opaque error.
    assert result.applied == 0
    assert len(result.failures) == 2
    assert result.partial is False


def test_editing_nothing_is_a_no_op_not_an_error(bulk):
    result = bulk.edit(ALICE, [], ItemFields(is_for_trade=True))
    assert result.requested == 0
    assert result.applied == 0


# --- bulk delete ---------------------------------------------------------------------

def test_deleting_removes_every_selected_row(bulk, svc, catalog, db):
    items = add_range(svc, catalog, 4)
    result = bulk.delete(ALICE, [i.id for i in items[:3]])

    assert result.applied == 3
    assert InventoryRepository(db).count_for_user(ALICE) == 1


def test_deleting_a_row_twice_reports_the_second_as_missing(bulk, svc, catalog):
    item = add_range(svc, catalog, 1)[0]
    bulk.delete(ALICE, [item.id])
    result = bulk.delete(ALICE, [item.id])

    assert result.applied == 0
    assert result.failures[0].code == "inventory_item_not_found"


def test_deleting_updates_completion(bulk, svc, catalog, db):
    """Each row goes through the same service the single-row path uses, so the projection is
    recomputed in the same transaction as every one of them — a bulk delete cannot leave
    completion claiming cards the collector no longer owns."""
    from app.repositories.set_completion_repository import SetCompletionRepository
    from app.repositories.set_repository import SetRepository
    from app.services.completion_service import CompletionService

    items = add_range(svc, catalog, 3)
    completion = CompletionService(SetCompletionRepository(db), SetRepository(db))
    assert completion.view(ALICE)[0].owned_cards == 3

    bulk.delete(ALICE, [i.id for i in items])

    views = completion.view(ALICE)
    assert views == [] or views[0].owned_cards == 0


def test_a_partial_delete_reports_both_halves(bulk, svc, catalog, db):
    items = add_range(svc, catalog, 3)
    result = bulk.delete(ALICE, [items[0].id, "no-such-row", items[2].id])

    assert result.applied == 2
    assert result.partial is True
    assert [f.item_id for f in result.failures] == ["no-such-row"]
    assert InventoryRepository(db).count_for_user(ALICE) == 1
