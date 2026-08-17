"""The inventory API.

The bolt requires an explicit cross-user access test for **every** endpoint, so there is one
per route below — each asserting 404 rather than 403.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.security import Principal, verify_token
from test_inventory import ALICE, BOB, seed_catalog


def principal(sub: str) -> Principal:
    return Principal(sub=sub, project_id="p", company_id="c", email=None,
                     username=None, scope="", token_type="access")


@pytest.fixture()
def catalog(db):
    return seed_catalog(db, card_count=3)


@pytest.fixture()
def api(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[verify_token] = lambda: principal(ALICE)
    yield TestClient(app)
    app.dependency_overrides.clear()


def as_bob():
    app.dependency_overrides[verify_token] = lambda: principal(BOB)


def test_add_returns_201_and_the_row(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    response = api.post("/api/v1/inventory", json={"printing_id": pid, "quantity": 2})

    assert response.status_code == 201
    body = response.json()
    assert body["merged"] is False
    assert body["item"]["quantity"] == 2
    assert body["item"]["condition"] == "near_mint"


def test_second_add_reports_merged(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    api.post("/api/v1/inventory", json={"printing_id": pid})
    body = api.post("/api/v1/inventory", json={"printing_id": pid}).json()

    # The fast-add flow shows this so a collector sees "now 2" rather than wondering where
    # the second row went.
    assert body["merged"] is True
    assert body["item"]["quantity"] == 2


def test_unknown_printing_is_404_with_a_stable_code(api, catalog):
    response = api.post("/api/v1/inventory", json={"printing_id": "nope"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "printing_not_found"


def test_invalid_quantity_is_rejected_by_validation(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    assert api.post("/api/v1/inventory", json={"printing_id": pid, "quantity": 0}).status_code == 422


def test_list_returns_only_the_callers_items(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    api.post("/api/v1/inventory", json={"printing_id": pid})

    as_bob()
    assert api.get("/api/v1/inventory").json()["total"] == 0


def test_patch_edits(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    item_id = api.post("/api/v1/inventory", json={"printing_id": pid}).json()["item"]["id"]

    body = api.patch(f"/api/v1/inventory/{item_id}", json={"quantity": 6, "notes": "box 1"}).json()
    assert body["quantity"] == 6
    assert body["notes"] == "box 1"


def test_delete_removes(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    item_id = api.post("/api/v1/inventory", json={"printing_id": pid}).json()["item"]["id"]

    assert api.delete(f"/api/v1/inventory/{item_id}").status_code == 204
    assert api.get("/api/v1/inventory").json()["total"] == 0


def test_adjust_applies_a_delta(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    item_id = api.post("/api/v1/inventory",
                       json={"printing_id": pid, "quantity": 3}).json()["item"]["id"]

    response = api.post(f"/api/v1/inventory/{item_id}/adjust",
                        json={"delta": -1, "expected_quantity": 3})

    assert response.status_code == 200
    body = response.json()
    assert body == {"item_id": item_id, "quantity": 2, "deleted": False}


def test_adjust_to_zero_reports_the_row_gone(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    item_id = api.post("/api/v1/inventory", json={"printing_id": pid}).json()["item"]["id"]

    body = api.post(f"/api/v1/inventory/{item_id}/adjust",
                    json={"delta": -1, "expected_quantity": 1}).json()

    # `deleted` is what lets the client drop the row rather than render a zero.
    assert body["deleted"] is True
    assert body["quantity"] == 0
    assert api.get("/api/v1/inventory").json()["total"] == 0


def test_adjust_refuses_a_stale_expectation_with_both_numbers(api, catalog):
    """The 409 carries `expected` and `actual` so the UI can say what it thought and what it
    found. "Could not undo" on its own leaves the collector unable to tell whether their
    collection is now right — story 018 rules that out."""
    pid = catalog["printings"]["BS1-001:common"]
    item_id = api.post("/api/v1/inventory", json={"printing_id": pid}).json()["item"]["id"]
    api.post("/api/v1/inventory", json={"printing_id": pid, "quantity": 4})

    response = api.post(f"/api/v1/inventory/{item_id}/adjust",
                        json={"delta": -1, "expected_quantity": 1})

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "inventory_item_changed"
    assert error["details"] == {"expected": 1, "actual": 5}


def test_adjust_rejects_a_zero_delta(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    item_id = api.post("/api/v1/inventory", json={"printing_id": pid}).json()["item"]["id"]

    response = api.post(f"/api/v1/inventory/{item_id}/adjust",
                        json={"delta": 0, "expected_quantity": 1})
    assert response.status_code == 400


def test_adjust_rejects_a_delta_outside_the_schema_range(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    item_id = api.post("/api/v1/inventory", json={"printing_id": pid}).json()["item"]["id"]

    response = api.post(f"/api/v1/inventory/{item_id}/adjust",
                        json={"delta": 10_001, "expected_quantity": 1})
    assert response.status_code == 422


def test_adjust_on_an_unknown_item_is_404(api, catalog):
    response = api.post("/api/v1/inventory/nope/adjust",
                        json={"delta": -1, "expected_quantity": 1})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "inventory_item_not_found"


def test_completion_reflects_the_write_immediately(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    api.post("/api/v1/inventory", json={"printing_id": pid, "quantity": 3})

    body = api.get("/api/v1/completion").json()
    assert body["total_items"] == 1
    assert body["total_quantity"] == 3
    (entry,) = body["sets"]
    assert entry["set_code"] == "FE01"
    assert entry["owned_cards"] == 1
    assert entry["card_count"] == 3


# --- cross-user access: one per endpoint --------------------------------------------

def test_cross_user_patch_is_404(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    item_id = api.post("/api/v1/inventory", json={"printing_id": pid}).json()["item"]["id"]

    as_bob()
    response = api.patch(f"/api/v1/inventory/{item_id}", json={"quantity": 99})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "inventory_item_not_found"


def test_cross_user_delete_is_404(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    item_id = api.post("/api/v1/inventory", json={"printing_id": pid}).json()["item"]["id"]

    as_bob()
    assert api.delete(f"/api/v1/inventory/{item_id}").status_code == 404


def test_cross_user_adjust_is_404_not_409(api, catalog):
    """A 409 would report the row's actual quantity — so for a row the caller does not own it
    has to be the same 404 a missing row gets, or the endpoint becomes a read primitive over
    other people's collections."""
    pid = catalog["printings"]["BS1-001:common"]
    item_id = api.post("/api/v1/inventory",
                       json={"printing_id": pid, "quantity": 3}).json()["item"]["id"]

    as_bob()
    response = api.post(f"/api/v1/inventory/{item_id}/adjust",
                        json={"delta": -1, "expected_quantity": 3})
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "inventory_item_not_found"
    # And it must carry no `details` — that is where the 409 puts the actual quantity.
    assert error["details"] == {}


def test_cross_user_list_shows_nothing(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    api.post("/api/v1/inventory", json={"printing_id": pid})

    as_bob()
    assert api.get("/api/v1/inventory").json()["items"] == []


def test_cross_user_completion_is_empty(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    api.post("/api/v1/inventory", json={"printing_id": pid})

    as_bob()
    body = api.get("/api/v1/completion").json()
    assert body["total_items"] == 0
    assert all(s["owned_cards"] == 0 for s in body["sets"])


def test_cross_user_add_does_not_merge_into_another_user(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    api.post("/api/v1/inventory", json={"printing_id": pid})

    as_bob()
    body = api.post("/api/v1/inventory", json={"printing_id": pid}).json()
    assert body["merged"] is False
    assert body["item"]["quantity"] == 1
