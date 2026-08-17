"""Sealed inventory and the wishlist — bolt 007, stories 025 and 026.

Two refusals carry this bolt, and both are things the code deliberately does *not* do:

* **Opening a box creates no singles.** The expected distribution is never the actual pull, so
  generated cards would be wrong every time — and wrong in a way the collector has to hunt down.
* **Acquiring a wished printing does not clear the wish.** It reports the overlap so the UI can
  prompt. Wanting a second copy is legitimate, and silently deleting stated intent is not recoverable.

Plus the guarantee story 025 exists for: sealed holdings appear in neither `/collection` nor any
completion figure, which is true because they are not in the table those queries read.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.sealed_product import SealedProduct
from app.repositories.inventory_repository import InventoryRepository
from app.security import Principal, verify_token
from app.services.sealed_service import (
    SealedFields, SealedItemNotFound, SealedProductNotFound, SealedService,
)
from app.services.wishlist_service import (
    AlreadyWished, InvalidWish, WishFields, WishlistService, WishNotFound,
)
from test_inventory import ALICE, BOB, build_service, seed_catalog


def principal(sub: str) -> Principal:
    return Principal(sub=sub, project_id="p", company_id="c", email=None,
                     username=None, scope="", token_type="access")


@pytest.fixture()
def catalog(db):
    return seed_catalog(db, card_count=3)


@pytest.fixture()
def product(db, catalog):
    row = SealedProduct(
        set_id=catalog["set"].id, kind="booster_box", name="Base Set Booster Box",
    )
    db.add(row)
    db.commit()
    return row


@pytest.fixture()
def other_product(db, catalog):
    row = SealedProduct(set_id=catalog["set"].id, kind="booster_pack", name="Base Set Pack")
    db.add(row)
    db.commit()
    return row


@pytest.fixture()
def sealed(db):
    return SealedService(db)


@pytest.fixture()
def wishes(db):
    return WishlistService(db)


@pytest.fixture()
def api(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[verify_token] = lambda: principal(ALICE)
    yield TestClient(app)
    app.dependency_overrides.clear()


def as_bob():
    app.dependency_overrides[verify_token] = lambda: principal(BOB)


# --- sealed: adding and merging ------------------------------------------------------

def test_adding_sealed_product(sealed, product):
    result = sealed.add(ALICE, sealed_product_id=product.id, quantity=2)
    assert result.merged is False
    assert result.item.quantity == 2
    assert result.item.is_sealed is True


def test_adding_the_same_product_twice_merges(sealed, product):
    sealed.add(ALICE, sealed_product_id=product.id, quantity=2)
    second = sealed.add(ALICE, sealed_product_id=product.id, quantity=3)

    assert second.merged is True
    assert second.item.quantity == 5
    assert len(sealed.list_for_user(ALICE)) == 1


def test_a_sealed_and_an_opened_copy_stay_separate(sealed, product):
    """`is_sealed` is part of the unique key, so the two states are different holdings. Merging
    them would make "how many are still sealed" unanswerable, which is the main thing this table
    is for."""
    sealed.add(ALICE, sealed_product_id=product.id, quantity=2, is_sealed=True)
    sealed.add(ALICE, sealed_product_id=product.id, quantity=1, is_sealed=False)

    items = sealed.list_for_user(ALICE)
    assert len(items) == 2
    assert {i.is_sealed for i in items} == {True, False}


def test_an_unknown_product_is_a_404(sealed):
    with pytest.raises(SealedProductNotFound):
        sealed.add(ALICE, sealed_product_id="nope")


def test_sealed_holdings_are_owner_scoped(sealed, product):
    sealed.add(ALICE, sealed_product_id=product.id)
    assert sealed.list_for_user(BOB) == []


def test_another_users_sealed_item_is_a_404_not_a_403(sealed, product):
    item = sealed.add(ALICE, sealed_product_id=product.id).item
    with pytest.raises(SealedItemNotFound):
        sealed.get(BOB, item.id)
    with pytest.raises(SealedItemNotFound):
        sealed.remove(BOB, item.id)


# --- sealed: opening -----------------------------------------------------------------

def test_opening_creates_no_singles(sealed, product, db):
    """**The refusal this bolt is built around.** A box has an expected distribution and an actual
    pull, and they are never the same — so inventing cards would be wrong every single time, and
    wrong in a way the collector has to find and undo one row at a time."""
    item = sealed.add(ALICE, sealed_product_id=product.id).item
    sealed.open(ALICE, item.id)

    assert InventoryRepository(db).count_for_user(ALICE) == 0


def test_opening_the_whole_holding_flips_it_in_place(sealed, product):
    """In place, so the id, cost basis and acquisition date survive. Delete-and-recreate would
    lose what you paid for the box, which is the one number that made recording it worthwhile."""
    item = sealed.add(
        ALICE, sealed_product_id=product.id, quantity=2,
        fields=SealedFields(acquired_unit_price_cents=9_000, acquired_currency="EUR"),
    ).item

    opened = sealed.open(ALICE, item.id, quantity=2)

    assert opened.id == item.id
    assert opened.is_sealed is False
    assert opened.acquired_unit_price_cents == 9_000


def test_opening_one_of_several_splits_the_holding(sealed, product):
    item = sealed.add(ALICE, sealed_product_id=product.id, quantity=3).item

    opened = sealed.open(ALICE, item.id, quantity=1)

    assert opened.quantity == 1
    assert opened.is_sealed is False
    remaining = [i for i in sealed.list_for_user(ALICE) if i.is_sealed]
    assert remaining[0].quantity == 2


def test_opening_merges_into_an_existing_opened_holding(sealed, product):
    sealed.add(ALICE, sealed_product_id=product.id, quantity=1, is_sealed=False)
    still_sealed = sealed.add(ALICE, sealed_product_id=product.id, quantity=2).item

    sealed.open(ALICE, still_sealed.id, quantity=1)

    opened = [i for i in sealed.list_for_user(ALICE) if not i.is_sealed]
    assert len(opened) == 1
    assert opened[0].quantity == 2


def test_opening_every_copy_removes_the_sealed_row(sealed, product):
    """Rather than leaving a zero. Same rule as `inventory_items`: a zero-quantity holding is a
    deletion that did not happen."""
    sealed.add(ALICE, sealed_product_id=product.id, quantity=1, is_sealed=False)
    still_sealed = sealed.add(ALICE, sealed_product_id=product.id, quantity=2).item

    sealed.open(ALICE, still_sealed.id, quantity=2)

    assert all(not i.is_sealed for i in sealed.list_for_user(ALICE))
    assert len(sealed.list_for_user(ALICE)) == 1


def test_opening_an_already_opened_holding_is_a_no_op(sealed, product):
    """Idempotent, per story 025's edge-case table: the requested end state is already true, so
    this is a success rather than an error."""
    item = sealed.add(ALICE, sealed_product_id=product.id, is_sealed=False).item
    again = sealed.open(ALICE, item.id)
    assert again.id == item.id
    assert again.quantity == 1


def test_opening_more_than_you_hold_opens_what_you_hold(sealed, product):
    item = sealed.add(ALICE, sealed_product_id=product.id, quantity=2).item
    opened = sealed.open(ALICE, item.id, quantity=99)
    assert opened.quantity == 2


def test_sealed_never_touches_completion(sealed, product, db, catalog):
    """Story 025's third criterion, and the reason sealed lives in its own table: it is true by
    construction rather than by every query remembering to filter."""
    from app.repositories.set_completion_repository import SetCompletionRepository
    from app.repositories.set_repository import SetRepository
    from app.services.completion_service import CompletionService

    sealed.add(ALICE, sealed_product_id=product.id, quantity=5)

    completion = CompletionService(SetCompletionRepository(db), SetRepository(db))
    assert completion.view(ALICE) == []


# --- wishlist ------------------------------------------------------------------------

def test_adding_a_wish(wishes, catalog):
    item = wishes.add(
        ALICE, printing_id=catalog["printings"]["BS1-001:common"],
        desired_quantity=2, priority="high",
    )
    assert item.desired_quantity == 2
    assert item.priority == "high"


def test_a_printing_cannot_be_wished_twice(wishes, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    wishes.add(ALICE, printing_id=pid)
    with pytest.raises(AlreadyWished):
        wishes.add(ALICE, printing_id=pid)


def test_two_users_can_wish_the_same_printing(wishes, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    wishes.add(ALICE, printing_id=pid)
    wishes.add(BOB, printing_id=pid)
    assert len(wishes.list_for_user(ALICE)) == 1
    assert len(wishes.list_for_user(BOB)) == 1


def test_wishing_a_printing_you_already_own_is_allowed(wishes, catalog, db):
    """Wanting a second copy is legitimate — a playset, a better condition, a spare to trade."""
    pid = catalog["printings"]["BS1-001:common"]
    build_service(db).add(ALICE, printing_id=pid)

    assert wishes.add(ALICE, printing_id=pid) is not None


def test_a_bare_number_is_not_a_price(wishes, catalog):
    """Story 026 rejects it outright, and the schema has a CHECK behind this. A maximum of "500"
    is meaningless without knowing whether that is euros or yen."""
    pid = catalog["printings"]["BS1-001:common"]
    with pytest.raises(InvalidWish):
        wishes.add(ALICE, printing_id=pid, max_price_cents=500)


def test_a_currency_with_no_amount_is_also_refused(wishes, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    with pytest.raises(InvalidWish):
        wishes.add(ALICE, printing_id=pid, max_price_currency="EUR")


def test_a_complete_price_is_accepted(wishes, catalog):
    item = wishes.add(
        ALICE, printing_id=catalog["printings"]["BS1-001:common"],
        max_price_cents=1_500, max_price_currency="EUR",
    )
    assert item.max_price_cents == 1_500


def test_an_unknown_priority_is_refused(wishes, catalog):
    with pytest.raises(InvalidWish):
        wishes.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"], priority="urgent")


def test_an_unknown_printing_is_refused(wishes):
    with pytest.raises(InvalidWish):
        wishes.add(ALICE, printing_id="nope")


def test_editing_validates_the_merged_state_not_the_patch(wishes, catalog):
    """Clearing only the currency would leave a price with no currency — half a price, which
    looks like a real one. Validating the patch alone would not catch it."""
    item = wishes.add(
        ALICE, printing_id=catalog["printings"]["BS1-001:common"],
        max_price_cents=1_000, max_price_currency="EUR",
    )
    with pytest.raises(InvalidWish):
        wishes.edit(ALICE, item.id, WishFields(desired_quantity=0))


def test_another_users_wish_is_a_404(wishes, catalog):
    item = wishes.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    with pytest.raises(WishNotFound):
        wishes.get(BOB, item.id)
    with pytest.raises(WishNotFound):
        wishes.remove(BOB, item.id)


def test_acquiring_reports_the_overlap_and_clears_nothing(wishes, catalog, db):
    """**The second refusal.** A collector may want a second copy, or a better condition. Deleting
    their stated intent because a row appeared elsewhere loses information they cannot recover and
    never agreed to lose — so this reports, and the UI prompts."""
    pid = catalog["printings"]["BS1-001:common"]
    wishes.add(ALICE, printing_id=pid, desired_quantity=2)
    build_service(db).add(ALICE, printing_id=pid)

    overlap = wishes.acquired_but_still_wished(ALICE)
    assert len(overlap) == 1
    # Still there. Nothing was cleared.
    assert len(wishes.list_for_user(ALICE)) == 1


def test_the_overlap_is_owner_scoped(wishes, catalog, db):
    pid = catalog["printings"]["BS1-001:common"]
    wishes.add(ALICE, printing_id=pid)
    build_service(db).add(BOB, printing_id=pid)

    assert wishes.acquired_but_still_wished(ALICE) == []


# --- over HTTP -----------------------------------------------------------------------

def test_sealed_api_round_trip(api, product):
    created = api.post("/api/v1/sealed", json={
        "sealed_product_id": product.id, "quantity": 2, "acquired_unit_price_cents": 9_000,
        "acquired_currency": "EUR",
    })
    assert created.status_code == 201
    assert created.json()["name"] == "Base Set Booster Box"

    listed = api.get("/api/v1/sealed").json()
    assert listed["total"] == 1
    assert listed["sealed_count"] == 2
    assert listed["opened_count"] == 0


def test_opening_over_http_moves_the_counts(api, product):
    item_id = api.post("/api/v1/sealed",
                       json={"sealed_product_id": product.id, "quantity": 2}).json()["id"]

    api.post(f"/api/v1/sealed/{item_id}/open?quantity=1")

    listed = api.get("/api/v1/sealed").json()
    assert listed["sealed_count"] == 1
    assert listed["opened_count"] == 1


def test_cross_user_sealed_list_is_empty(api, product):
    api.post("/api/v1/sealed", json={"sealed_product_id": product.id})
    as_bob()
    assert api.get("/api/v1/sealed").json()["total"] == 0


def test_cross_user_sealed_open_is_404(api, product):
    item_id = api.post("/api/v1/sealed",
                       json={"sealed_product_id": product.id}).json()["id"]
    as_bob()
    assert api.post(f"/api/v1/sealed/{item_id}/open").status_code == 404


def test_cross_user_sealed_patch_is_404(api, product):
    item_id = api.post("/api/v1/sealed",
                       json={"sealed_product_id": product.id}).json()["id"]
    as_bob()
    assert api.patch(f"/api/v1/sealed/{item_id}", json={"quantity": 99}).status_code == 404


def test_cross_user_sealed_delete_is_404(api, product):
    item_id = api.post("/api/v1/sealed",
                       json={"sealed_product_id": product.id}).json()["id"]
    as_bob()
    assert api.delete(f"/api/v1/sealed/{item_id}").status_code == 404


def test_wishlist_api_round_trip(api, catalog):
    created = api.post("/api/v1/wishlist", json={
        "printing_id": catalog["printings"]["BS1-001:common"],
        "desired_quantity": 2, "priority": "high",
        "max_price_cents": 1_500, "max_price_currency": "EUR",
    })
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Card 1"
    assert body["owned"] is False

    assert api.get("/api/v1/wishlist").json()["total"] == 1


def test_a_duplicate_wish_is_409(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    api.post("/api/v1/wishlist", json={"printing_id": pid})
    response = api.post("/api/v1/wishlist", json={"printing_id": pid})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_wished"


def test_half_a_price_is_400_over_http(api, catalog):
    response = api.post("/api/v1/wishlist", json={
        "printing_id": catalog["printings"]["BS1-001:common"], "max_price_cents": 500,
    })
    assert response.status_code == 400


def test_the_wishlist_flags_what_is_now_owned(api, catalog, db):
    pid = catalog["printings"]["BS1-001:common"]
    api.post("/api/v1/wishlist", json={"printing_id": pid})
    build_service(db).add(ALICE, printing_id=pid)

    body = api.get("/api/v1/wishlist").json()
    assert body["acquired_count"] == 1
    assert body["items"][0]["owned"] is True
    # Flagged, not removed.
    assert body["total"] == 1


def test_cross_user_wishlist_is_empty(api, catalog):
    api.post("/api/v1/wishlist", json={"printing_id": catalog["printings"]["BS1-001:common"]})
    as_bob()
    assert api.get("/api/v1/wishlist").json()["total"] == 0


def test_cross_user_wish_patch_is_404(api, catalog):
    item_id = api.post("/api/v1/wishlist", json={
        "printing_id": catalog["printings"]["BS1-001:common"],
    }).json()["id"]
    as_bob()
    assert api.patch(f"/api/v1/wishlist/{item_id}", json={"priority": "low"}).status_code == 404


def test_cross_user_wish_delete_is_404(api, catalog):
    item_id = api.post("/api/v1/wishlist", json={
        "printing_id": catalog["printings"]["BS1-001:common"],
    }).json()["id"]
    as_bob()
    assert api.delete(f"/api/v1/wishlist/{item_id}").status_code == 404


def test_sealed_never_appears_in_the_collection_table(api, product, catalog):
    """The guarantee story 025 exists for, asserted from the outside."""
    api.post("/api/v1/sealed", json={"sealed_product_id": product.id, "quantity": 3})
    api.post("/api/v1/inventory", json={"printing_id": catalog["printings"]["BS1-001:common"]})

    body = api.get("/api/v1/collection").json()
    assert body["total"] == 1
    assert all(row["name"] != "Base Set Booster Box" for row in body["items"])
