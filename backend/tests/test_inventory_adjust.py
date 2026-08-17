"""The undo primitive — ADR-005, story 018.

`POST /inventory/{id}/adjust` exists because undo has to reverse **a delta rather than a row**,
and has to **refuse rather than guess** when the holding moved outside the session. Those two
requirements are what the tests below are about; everything else here is the guard rail that
keeps the compare-and-swap from degrading into a read-then-write.

The one that matters most is `test_concurrent_undos_only_one_wins`. Every sequential assertion
in this file also passes against a read-compare-write implementation, which is precisely the
race bolt 004's atomic upsert eliminated and which ADR-005 refuses to reintroduce one layer up.
Two real threads on two real connections are the only way to tell the two apart.
"""
from __future__ import annotations

import threading

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.inventory_item import InventoryItem
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.set_completion_repository import SetCompletionRepository
from app.repositories.set_repository import SetRepository
from app.services.completion_service import CompletionService
from app.services.inventory_service import (
    ItemChanged,
    ItemNotFound,
    QuantityOutOfRange,
)
# Sibling test module, as in `test_inventory_api.py` and `test_set_completion.py` — the catalog
# fixture and the two user subs live in one place so every inventory suite shares them.
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


# --- reversing a delta, not a row ----------------------------------------------------

def test_undoing_one_of_three_adds_leaves_the_holding(svc, catalog, db):
    """The rule the bolt exists for.

    Emptying a box means adding the same printing repeatedly. Undo has to take back *one add*
    — "reverse to the quantity before the add" would delete a holding built from three.
    """
    pid = catalog["printings"]["BS1-001:common"]
    item = svc.add(ALICE, printing_id=pid).item
    svc.add(ALICE, printing_id=pid)
    svc.add(ALICE, printing_id=pid)

    result = svc.adjust(ALICE, item.id, delta=-1, expected_quantity=3)

    assert result.deleted is False
    assert result.quantity == 2
    assert InventoryRepository(db).count_for_user(ALICE) == 1


def test_a_positive_delta_adds(svc, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    item = svc.add(ALICE, printing_id=pid, quantity=2).item

    result = svc.adjust(ALICE, item.id, delta=3, expected_quantity=2)
    assert result.quantity == 5


def test_reaching_zero_removes_the_row(svc, catalog, db):
    """Bolt 004 is explicit that a zero-quantity row is a deletion that did not happen — there
    is a `quantity > 0` CHECK behind that. Undoing the add that created a holding must therefore
    remove it, not leave a zero for the client to render as "you own none of this"."""
    pid = catalog["printings"]["BS1-001:common"]
    item = svc.add(ALICE, printing_id=pid).item

    result = svc.adjust(ALICE, item.id, delta=-1, expected_quantity=1)

    assert result.deleted is True
    assert result.quantity == 0
    assert InventoryRepository(db).get(ALICE, item.id) is None


def test_the_quantity_is_read_back_after_the_write(svc, catalog, db):
    """The ORM identity map holds the pre-update row, so a caller reading through the same
    session would otherwise see the old number — the trap `upsert_merge` documents, which is why
    `compare_and_adjust` expires the session."""
    pid = catalog["printings"]["BS1-001:common"]
    item = svc.add(ALICE, printing_id=pid, quantity=4).item

    svc.adjust(ALICE, item.id, delta=-2, expected_quantity=4)

    assert InventoryRepository(db).get(ALICE, item.id).quantity == 2


# --- refusing rather than guessing ---------------------------------------------------

def test_a_stale_expectation_is_refused_with_both_numbers(svc, catalog, db):
    """Somebody moved the row in another tab. Story 018 requires a refusal that explains
    itself, so the collector knows whether their collection is now right."""
    pid = catalog["printings"]["BS1-001:common"]
    item = svc.add(ALICE, printing_id=pid).item
    # The "other tab": the holding reaches 5 while the session still believes it is 1.
    svc.add(ALICE, printing_id=pid, quantity=4)

    with pytest.raises(ItemChanged) as caught:
        svc.adjust(ALICE, item.id, delta=-1, expected_quantity=1)

    assert caught.value.expected == 1
    assert caught.value.actual == 5
    assert caught.value.status == 409
    # Nothing was changed. A refusal that half-applied would be worse than a wrong guess.
    assert InventoryRepository(db).get(ALICE, item.id).quantity == 5


def test_another_users_item_is_a_404_not_a_409(svc, catalog):
    """A 409 carries the actual quantity. Returning one for a row the caller does not own would
    hand a stranger both an existence oracle and its contents — so the mismatch has to be
    resolved by an owner-scoped read, and a stranger gets the same 404 a missing row gets."""
    pid = catalog["printings"]["BS1-001:common"]
    alices = svc.add(ALICE, printing_id=pid).item

    with pytest.raises(ItemNotFound):
        svc.adjust(BOB, alices.id, delta=-1, expected_quantity=1)


def test_another_users_item_is_not_modified(svc, catalog, db):
    pid = catalog["printings"]["BS1-001:common"]
    alices = svc.add(ALICE, printing_id=pid, quantity=3).item

    with pytest.raises(ItemNotFound):
        svc.adjust(BOB, alices.id, delta=-3, expected_quantity=3)

    assert InventoryRepository(db).get(ALICE, alices.id).quantity == 3


def test_an_unknown_item_is_a_404(svc, catalog):
    with pytest.raises(ItemNotFound):
        svc.adjust(ALICE, "no-such-item", delta=-1, expected_quantity=1)


# --- the guard rails -----------------------------------------------------------------

def test_a_zero_delta_is_refused(svc, catalog):
    """There is no such thing as a zero adjustment, and accepting one would let a caller use
    this endpoint as an existence probe that leaves no trace."""
    pid = catalog["printings"]["BS1-001:common"]
    item = svc.add(ALICE, printing_id=pid).item

    with pytest.raises(QuantityOutOfRange):
        svc.adjust(ALICE, item.id, delta=0, expected_quantity=1)


def test_an_oversized_delta_is_refused(svc, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    item = svc.add(ALICE, printing_id=pid).item

    with pytest.raises(QuantityOutOfRange):
        svc.adjust(ALICE, item.id, delta=-99_999, expected_quantity=1)


def test_an_adjustment_below_zero_is_refused_before_it_is_attempted(svc, catalog, db):
    pid = catalog["printings"]["BS1-001:common"]
    item = svc.add(ALICE, printing_id=pid, quantity=2).item

    with pytest.raises(QuantityOutOfRange):
        svc.adjust(ALICE, item.id, delta=-5, expected_quantity=2)

    assert InventoryRepository(db).get(ALICE, item.id).quantity == 2


# --- the projection ------------------------------------------------------------------

def test_completion_follows_an_undo(svc, completion, catalog):
    """Completion is recomputed in the same transaction as the write, so it can never disagree
    with inventory — including when the write is an undo that deletes the last copy."""
    pid = catalog["printings"]["BS1-001:common"]
    item = svc.add(ALICE, printing_id=pid).item
    assert completion.view(ALICE)[0].owned_cards == 1

    svc.adjust(ALICE, item.id, delta=-1, expected_quantity=1)

    views = completion.view(ALICE)
    assert views == [] or views[0].owned_cards == 0


def test_completion_is_unchanged_when_a_duplicate_is_undone(svc, completion, catalog):
    """Undoing the second copy of a card still leaves the card owned. Completion counts distinct
    cards, so it must not move."""
    pid = catalog["printings"]["BS1-001:common"]
    item = svc.add(ALICE, printing_id=pid).item
    svc.add(ALICE, printing_id=pid)

    svc.adjust(ALICE, item.id, delta=-1, expected_quantity=2)

    row = completion.view(ALICE)[0]
    assert row.owned_cards == 1
    assert row.total_quantity == 1


# --- the repository primitive --------------------------------------------------------

def test_compare_and_adjust_will_not_say_which_half_failed(svc, catalog, db):
    """`compare_and_adjust` deliberately cannot distinguish a wrong owner from a stale
    expectation: ownership and concurrency are one `WHERE` clause, which is what removes the
    window between checking them. The service resolves the difference afterwards."""
    pid = catalog["printings"]["BS1-001:common"]
    item = svc.add(ALICE, printing_id=pid).item
    repo = InventoryRepository(db)

    assert repo.compare_and_adjust(BOB, item.id, delta=-1, expected=1) is False
    assert repo.compare_and_adjust(ALICE, item.id, delta=-1, expected=7) is False
    assert repo.compare_and_adjust(ALICE, item.id, delta=1, expected=1) is True


def test_compare_and_adjust_writes_one_statement(svc, catalog, db, engine):
    """A read-then-write would show up here as a SELECT between the two. The point of the
    endpoint is that there is nothing between them, because there is no 'between'."""
    from conftest import count_writes

    pid = catalog["printings"]["BS1-001:common"]
    item = svc.add(ALICE, printing_id=pid, quantity=2).item

    with count_writes(engine) as statements:
        InventoryRepository(db).compare_and_adjust(ALICE, item.id, delta=-1, expected=2)

    assert len(statements) == 1, statements
    assert statements[0].lstrip().upper().startswith("UPDATE")


def test_reaching_zero_issues_a_delete_not_an_update(svc, catalog, db, engine):
    from conftest import count_writes

    pid = catalog["printings"]["BS1-001:common"]
    item = svc.add(ALICE, printing_id=pid).item

    with count_writes(engine) as statements:
        InventoryRepository(db).compare_and_adjust(ALICE, item.id, delta=-1, expected=1)

    assert len(statements) == 1, statements
    assert statements[0].lstrip().upper().startswith("DELETE")


# --- concurrency ---------------------------------------------------------------------

def test_concurrent_undos_only_one_wins(tmp_path, catalog):
    """**The assertion this endpoint exists for.**

    Two undos of the same add, racing — a held `Ctrl+Z`, or two tabs. Both carry the same
    `expected_quantity`, so at most one can match. A read-compare-write would let both read 2,
    both decide the row is unchanged, and both write 1 — losing a copy silently.

    SQLite on disk, two connections, a barrier to make the overlap real. This proves the
    statement is atomic; MySQL's own behaviour under the same race is verified separately by
    `scripts/verify_mysql.py`.
    """
    url = f"sqlite:///{tmp_path / 'concurrent_adjust.db'}"
    engine = create_engine(url, connect_args={"timeout": 30}, future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

    seed = Session()
    data = seed_catalog(seed)
    pid = data["printings"]["BS1-001:common"]
    item_id = build_service(seed).add(ALICE, printing_id=pid, quantity=2).item.id
    seed.close()

    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()

    def worker():
        session = Session()
        try:
            barrier.wait(timeout=10)
            build_service(session).adjust(ALICE, item_id, delta=-1, expected_quantity=2)
            verdict = "applied"
        except ItemChanged:
            verdict = "refused"
        except Exception as exc:  # noqa: BLE001 — surfaced through `outcomes`
            verdict = f"error: {type(exc).__name__}: {exc}"
        finally:
            session.close()
        with lock:
            outcomes.append(verdict)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    check = Session()
    rows = list(check.scalars(select(InventoryItem).where(InventoryItem.user_sub == ALICE)))
    check.close()
    engine.dispose()

    assert outcomes.count("applied") == 1, outcomes
    # The loser must be a refusal, not a crash and not a second success. A `database is locked`
    # here would mean the two statements are serialising by luck rather than by the WHERE clause.
    assert outcomes.count("refused") == 1, outcomes
    assert len(rows) == 1
    assert rows[0].quantity == 1, f"quantity was {rows[0].quantity}, expected 1"
