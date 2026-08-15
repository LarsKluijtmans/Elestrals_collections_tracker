"""Inventory writes: the merge invariant, ownership, and completion staying exact."""
from __future__ import annotations

import threading

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.importer.canonical import CanonicalCard, CanonicalPrinting
from app.models.card import Card
from app.models.inventory_item import InventoryItem
from app.models.set import Set
from app.repositories.card_repository import CardRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.printing_repository import PrintingRepository
from app.repositories.set_completion_repository import SetCompletionRepository
from app.repositories.set_repository import SetRepository
from app.services.catalog_upsert import CatalogUpsert
from app.services.completion_service import CompletionService
from app.services.inventory_service import (
    InventoryService,
    ItemFields,
    ItemNotFound,
    PrintingNotFound,
    QuantityOutOfRange,
)

ALICE = "user-alice"
BOB = "user-bob"


def build_service(db) -> InventoryService:
    return InventoryService(
        InventoryRepository(db),
        PrintingRepository(db),
        CompletionService(SetCompletionRepository(db), SetRepository(db)),
    )


def seed_catalog(db, *, card_count: int = 3) -> dict:
    set_row = Set(code="FE01", name="Base", card_count=card_count)
    db.add(set_row)
    db.commit()

    upsert = CatalogUpsert(CardRepository(db))
    printings: dict[str, str] = {}
    for n in range(1, card_count + 1):
        number = f"BS1-{n:03d}"
        upsert.upsert(
            CanonicalCard(
                set_code="FE01", collector_number=number, name=f"Card {n}",
                card_type="rune", rune_type="invoke",
                printings=(
                    CanonicalPrinting(rarity="common", finish="normal", language="en",
                                      edition="first"),
                    CanonicalPrinting(rarity="holo_rare", finish="foil", language="en",
                                      edition="first"),
                ),
            ),
            set_id=set_row.id,
        )
    for card in db.scalars(select(Card)):
        for printing in card.printings:
            printings[f"{card.collector_number}:{printing.rarity}"] = printing.id
    return {"set": set_row, "printings": printings}


@pytest.fixture()
def catalog(db):
    return seed_catalog(db)


@pytest.fixture()
def svc(db):
    return build_service(db)


# --- merge ---------------------------------------------------------------------------

def test_adding_the_same_printing_twice_merges(svc, catalog, db):
    pid = catalog["printings"]["BS1-001:common"]

    first = svc.add(ALICE, printing_id=pid)
    second = svc.add(ALICE, printing_id=pid)

    assert first.merged is False
    assert second.merged is True
    assert second.item.id == first.item.id
    assert second.item.quantity == 2
    assert InventoryRepository(db).count_for_user(ALICE) == 1


def test_different_conditions_are_different_rows(svc, catalog, db):
    pid = catalog["printings"]["BS1-001:common"]
    svc.add(ALICE, printing_id=pid, condition="near_mint")
    svc.add(ALICE, printing_id=pid, condition="lightly_played")
    assert InventoryRepository(db).count_for_user(ALICE) == 2


def test_two_graded_copies_stay_separate_rows(svc, catalog, db):
    """A PSA 9 and a PSA 10 are different objects — and so are two PSA 9s. Each has its own
    serial and its own value, and merging them would destroy that."""
    pid = catalog["printings"]["BS1-001:common"]

    svc.add(ALICE, printing_id=pid, is_graded=True, grader="PSA", grade=9)
    svc.add(ALICE, printing_id=pid, is_graded=True, grader="PSA", grade=10)
    svc.add(ALICE, printing_id=pid, is_graded=True, grader="PSA", grade=9)

    items = InventoryRepository(db).list_for_user(ALICE)
    assert len(items) == 3
    assert all(i.quantity == 1 for i in items)
    assert all(i.merge_condition is None for i in items)


def test_graded_and_ungraded_do_not_merge(svc, catalog, db):
    pid = catalog["printings"]["BS1-001:common"]
    svc.add(ALICE, printing_id=pid)
    svc.add(ALICE, printing_id=pid, is_graded=True, grader="PSA", grade=9)
    assert InventoryRepository(db).count_for_user(ALICE) == 2


def test_quantity_accumulates_by_the_amount_added(svc, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    svc.add(ALICE, printing_id=pid, quantity=3)
    result = svc.add(ALICE, printing_id=pid, quantity=4)
    assert result.item.quantity == 7


def test_concurrent_adds_produce_one_row(tmp_path, catalog):
    """The invariant the bolt exists for.

    A read-then-write passes every sequential test above and loses rows in production, because
    the fast-add flow fires concurrent requests by design. Two real threads on two real
    connections, so the atomic upsert is what resolves the race rather than luck.

    SQLite, not MySQL — this proves the statement is a single atomic upsert. MySQL's own
    `ON DUPLICATE KEY UPDATE` behaviour remains unverified until a server exists.
    """
    url = f"sqlite:///{tmp_path / 'concurrent.db'}"
    engine = create_engine(url, connect_args={"timeout": 30}, future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

    seed = Session()
    data = seed_catalog(seed)
    pid = data["printings"]["BS1-001:common"]
    seed.close()

    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def worker():
        session = Session()
        try:
            barrier.wait(timeout=10)
            build_service(session).add(ALICE, printing_id=pid)
        except Exception as exc:  # noqa: BLE001 — surfaced via `errors`
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, errors

    check = Session()
    rows = list(check.scalars(select(InventoryItem).where(InventoryItem.user_sub == ALICE)))
    check.close()
    engine.dispose()

    assert len(rows) == 1, "concurrent adds created two rows"
    assert rows[0].quantity == 2, f"quantity was {rows[0].quantity}, expected 2"


# --- ownership -----------------------------------------------------------------------

def test_another_users_item_is_a_404_not_a_403(svc, catalog):
    """Distinguishing 'gone' from 'not yours' is an enumeration oracle over the whole table."""
    pid = catalog["printings"]["BS1-001:common"]
    alices = svc.add(ALICE, printing_id=pid).item

    with pytest.raises(ItemNotFound):
        svc.edit(BOB, alices.id, ItemFields(quantity=99))
    with pytest.raises(ItemNotFound):
        svc.remove(BOB, alices.id)


def test_inventories_are_isolated(svc, catalog, db):
    pid = catalog["printings"]["BS1-001:common"]
    svc.add(ALICE, printing_id=pid)
    svc.add(BOB, printing_id=pid, quantity=5)

    repo = InventoryRepository(db)
    assert repo.count_for_user(ALICE) == 1
    assert repo.total_quantity(ALICE) == 1
    assert repo.total_quantity(BOB) == 5


def test_the_same_printing_merges_per_user_not_globally(svc, catalog, db):
    pid = catalog["printings"]["BS1-001:common"]
    svc.add(ALICE, printing_id=pid)
    svc.add(BOB, printing_id=pid)
    assert len(InventoryRepository(db).list_for_user(ALICE)) == 1
    assert len(InventoryRepository(db).list_for_user(BOB)) == 1


# --- edit / remove -------------------------------------------------------------------

def test_edit_updates_fields(svc, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    item = svc.add(ALICE, printing_id=pid).item

    edited = svc.edit(ALICE, item.id, ItemFields(quantity=5, notes="binder 2", is_for_trade=True))
    assert edited.quantity == 5
    assert edited.notes == "binder 2"
    assert edited.is_for_trade is True


def test_editing_a_condition_into_an_existing_row_merges_them(svc, catalog, db):
    """Two ungraded Near Mint rows for one printing is precisely the state the unique index
    exists to prevent, so the edit folds rather than failing."""
    pid = catalog["printings"]["BS1-001:common"]
    keep = svc.add(ALICE, printing_id=pid, condition="near_mint", quantity=2).item
    move = svc.add(ALICE, printing_id=pid, condition="lightly_played", quantity=3).item

    merged = svc.edit(ALICE, move.id, ItemFields(condition="near_mint"))

    assert merged.id == keep.id
    assert merged.quantity == 5
    assert InventoryRepository(db).count_for_user(ALICE) == 1


def test_remove_deletes_the_row(svc, catalog, db):
    pid = catalog["printings"]["BS1-001:common"]
    item = svc.add(ALICE, printing_id=pid).item

    svc.remove(ALICE, item.id)
    assert InventoryRepository(db).count_for_user(ALICE) == 0


def test_removing_twice_is_a_404(svc, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    item = svc.add(ALICE, printing_id=pid).item
    svc.remove(ALICE, item.id)
    with pytest.raises(ItemNotFound):
        svc.remove(ALICE, item.id)


# --- validation ----------------------------------------------------------------------

def test_unknown_printing_is_rejected(svc, catalog):
    with pytest.raises(PrintingNotFound):
        svc.add(ALICE, printing_id="does-not-exist")


def test_quantity_bounds(svc, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    with pytest.raises(QuantityOutOfRange):
        svc.add(ALICE, printing_id=pid, quantity=0)
    with pytest.raises(QuantityOutOfRange):
        svc.add(ALICE, printing_id=pid, quantity=10_001)
