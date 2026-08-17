"""The collection API — bolt 006 over HTTP.

Every user-owned endpoint gets an explicit cross-user test, as bolt 004 established and this bolt
inherits: **404, never 403**, because distinguishing "gone" from "not yours" is an enumeration
oracle over the whole table.

The other thing pinned here is that a filtered view is a *shareable artifact*: the filters go out
in the query string, come back in the response, and mean the same thing to a saved view.
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
    return seed_catalog(db, card_count=6)


@pytest.fixture()
def api(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[verify_token] = lambda: principal(ALICE)
    yield TestClient(app)
    app.dependency_overrides.clear()


def as_bob():
    app.dependency_overrides[verify_token] = lambda: principal(BOB)


def add(api, catalog, n=1, **body):
    return api.post("/api/v1/inventory", json={
        "printing_id": catalog["printings"][f"BS1-{n:03d}:common"], **body,
    }).json()["item"]


# --- the table -----------------------------------------------------------------------

def test_an_empty_collection_is_200_with_an_empty_page(api, catalog):
    body = api.get("/api/v1/collection").json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["next_cursor"] is None


def test_a_row_carries_its_catalog_fields(api, catalog):
    """Joined server-side, so drawing 50 rows is one request rather than one plus fifty. At the
    10,000-row scale this bolt targets, the waterfall is the difference between a table and a
    progress bar."""
    add(api, catalog, 1)
    (row,) = api.get("/api/v1/collection").json()["items"]

    assert row["name"] == "Card 1"
    assert row["set_code"] == "FE01"
    assert row["collector_number"] == "BS1-001"
    assert row["rarity"] == "common"
    assert row["alt_text"] == "Card 1 — FE01 common"


def test_filters_come_back_in_the_response(api, catalog):
    """So a client can prove the URL it holds and the rows it got agree — and so a saved view
    applied from the rail can be diffed against what is actually in effect."""
    add(api, catalog, 1, condition="damaged")
    body = api.get("/api/v1/collection?condition=damaged").json()

    assert body["filters"] == {"condition": ["damaged"]}
    assert body["sort"] == "added_desc"
    assert body["total"] == 1


def test_repeated_query_parameters_or_together(api, catalog):
    add(api, catalog, 1, condition="damaged")
    add(api, catalog, 2, condition="mint")
    add(api, catalog, 3, condition="near_mint")

    body = api.get("/api/v1/collection?condition=damaged&condition=mint").json()
    assert body["total"] == 2


def test_an_unknown_query_parameter_does_not_break_a_shared_link(api, catalog):
    # `?utm_source=twitter` on a link somebody shared must not 400.
    add(api, catalog, 1)
    assert api.get("/api/v1/collection?utm_source=twitter").status_code == 200


def test_an_invalid_filter_value_is_400_not_an_empty_list(api, catalog):
    response = api.get("/api/v1/collection?condition=mnt")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_an_unknown_sort_is_400_and_lists_the_valid_ones(api, catalog):
    response = api.get("/api/v1/collection?sort=by_vibes")
    assert response.status_code == 400
    assert "added_desc" in response.json()["error"]["details"]["allowed"]


def test_a_malformed_cursor_is_400(api, catalog):
    assert api.get("/api/v1/collection?cursor=!!!").status_code == 400


def test_paging_over_http_walks_every_row(api, catalog):
    for n in range(1, 6):
        add(api, catalog, n)

    seen, cursor = [], None
    for _ in range(10):
        url = "/api/v1/collection?limit=2" + (f"&cursor={cursor}" if cursor else "")
        body = api.get(url).json()
        seen.extend(r["id"] for r in body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert len(seen) == 5
    assert len(set(seen)) == 5


def test_cross_user_browse_shows_nothing(api, catalog):
    add(api, catalog, 1)
    as_bob()
    assert api.get("/api/v1/collection").json()["total"] == 0


# --- missing cards -------------------------------------------------------------------

def test_missing_lists_unowned_cards(api, catalog):
    add(api, catalog, 1)
    body = api.get("/api/v1/collection/missing/FE01").json()

    assert body["card_count"] == 6
    assert body["owned_cards"] == 1
    assert len(body["missing"]) == 5


def test_missing_from_an_unknown_set_is_404(api, catalog):
    assert api.get("/api/v1/collection/missing/NOPE").status_code == 404


def test_cross_user_missing_shows_the_whole_set(api, catalog):
    add(api, catalog, 1)
    as_bob()
    assert api.get("/api/v1/collection/missing/FE01").json()["owned_cards"] == 0


# --- selection and bulk --------------------------------------------------------------

def test_a_selection_count_answers_before_acting(api, catalog):
    """Story 022 requires the confirmation to *name the count*. A bulk-delete confirmation that
    says "delete these?" without saying how many is the one that gets clicked through."""
    for n in range(1, 4):
        add(api, catalog, n, condition="damaged")

    body = api.post("/api/v1/collection/selection/count",
                    json={"filters": {"condition": ["damaged"]}}).json()
    assert body["count"] == 3


def test_bulk_edit_by_filter(api, catalog):
    for n in range(1, 4):
        add(api, catalog, n)

    body = api.post("/api/v1/collection/bulk/edit", json={
        "filters": {}, "storage_location": "binder 2", "is_for_trade": True,
    }).json()

    assert body["applied"] == 3
    assert body["failures"] == []
    assert all(r["is_for_trade"] for r in api.get("/api/v1/collection").json()["items"])


def test_bulk_edit_by_explicit_ids(api, catalog):
    items = [add(api, catalog, n) for n in range(1, 4)]
    body = api.post("/api/v1/collection/bulk/edit", json={
        "item_ids": [items[0]["id"]], "is_for_trade": True,
    }).json()
    assert body["applied"] == 1


def test_a_partial_bulk_is_200_with_the_failures_named(api, catalog):
    """**200, not 207 and not 400.** The request was understood and acted on; `partial` in the
    body is the flag the UI reads. Failing the whole operation because one row moved is what
    story 022 rules out, and so is applying it silently."""
    items = [add(api, catalog, n) for n in range(1, 3)]

    response = api.post("/api/v1/collection/bulk/edit", json={
        "item_ids": [items[0]["id"], "no-such-row"], "is_for_trade": True,
    })

    assert response.status_code == 200
    body = response.json()
    assert body["requested"] == 2
    assert body["applied"] == 1
    assert body["partial"] is True
    assert body["failures"][0]["item_id"] == "no-such-row"
    assert body["failures"][0]["code"] == "inventory_item_not_found"


def test_bulk_delete_removes_the_selection(api, catalog):
    for n in range(1, 4):
        add(api, catalog, n)
    body = api.post("/api/v1/collection/bulk/delete", json={"filters": {}}).json()

    assert body["applied"] == 3
    assert api.get("/api/v1/collection").json()["total"] == 0


def test_a_bulk_request_with_no_selection_is_400(api, catalog):
    assert api.post("/api/v1/collection/bulk/delete", json={}).status_code == 400


def test_cross_user_bulk_edit_touches_nothing(api, catalog):
    mine = add(api, catalog, 1, storage_location="my binder")

    as_bob()
    body = api.post("/api/v1/collection/bulk/edit", json={
        "item_ids": [mine["id"]], "storage_location": "taken",
    }).json()
    assert body["applied"] == 0
    assert body["failures"][0]["code"] == "inventory_item_not_found"

    app.dependency_overrides[verify_token] = lambda: principal(ALICE)
    (row,) = api.get("/api/v1/collection").json()["items"]
    assert row["storage_location"] == "my binder"


def test_cross_user_bulk_delete_by_filter_deletes_nothing_of_mine(api, catalog):
    add(api, catalog, 1)
    as_bob()
    assert api.post("/api/v1/collection/bulk/delete", json={"filters": {}}).json()["applied"] == 0

    app.dependency_overrides[verify_token] = lambda: principal(ALICE)
    assert api.get("/api/v1/collection").json()["total"] == 1


# --- saved views ---------------------------------------------------------------------

def test_saving_and_applying_a_view(api, catalog):
    created = api.post("/api/v1/collection/views", json={
        "name": "Fire holos", "filters": {"element": ["fire"], "rarity": ["holo_rare"]},
        "sort": "name_asc", "density": "compact",
    })
    assert created.status_code == 201
    body = created.json()
    assert body["filters"] == {"element": ["fire"], "rarity": ["holo_rare"]}
    assert body["density"] == "compact"

    assert [v["name"] for v in api.get("/api/v1/collection/views").json()] == ["Fire holos"]


def test_a_view_stores_the_shape_the_url_serialises(api, catalog):
    """The property that keeps a saved view and a shared link meaning the same thing. Two
    encodings of one concept would drift, and the drift shows up as a view that restores
    something subtly different from the link."""
    api.post("/api/v1/collection/views",
             json={"name": "Damaged", "filters": {"condition": ["damaged"]}})
    (view,) = api.get("/api/v1/collection/views").json()

    add(api, catalog, 1, condition="damaged")
    add(api, catalog, 2)

    from urllib.parse import urlencode
    query = urlencode([(k, v) for k, vs in view["filters"].items() for v in vs])
    assert api.get(f"/api/v1/collection?{query}").json()["total"] == 1


def test_an_unknown_filter_in_a_view_is_dropped_at_save_time(api):
    """So what a view restores is exactly what it stored, and a view written by a later deploy
    still opens on an older one."""
    body = api.post("/api/v1/collection/views", json={
        "name": "Future", "filters": {"element": ["fire"], "sparkliness": ["high"]},
    }).json()
    assert body["filters"] == {"element": ["fire"]}


def test_duplicate_view_names_are_409(api):
    api.post("/api/v1/collection/views", json={"name": "Mine", "filters": {}})
    response = api.post("/api/v1/collection/views", json={"name": "Mine", "filters": {}})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "saved_view_name_taken"


def test_an_invalid_sort_on_a_view_is_400(api):
    response = api.post("/api/v1/collection/views",
                        json={"name": "Bad", "filters": {}, "sort": "by_vibes"})
    assert response.status_code == 400


def test_renaming_and_deleting_a_view(api):
    view_id = api.post("/api/v1/collection/views",
                       json={"name": "Old", "filters": {}}).json()["id"]

    renamed = api.patch(f"/api/v1/collection/views/{view_id}", json={"name": "New"})
    assert renamed.json()["name"] == "New"

    assert api.delete(f"/api/v1/collection/views/{view_id}").status_code == 204
    assert api.get("/api/v1/collection/views").json() == []


def test_cross_user_views_are_invisible(api):
    api.post("/api/v1/collection/views", json={"name": "Mine", "filters": {}})
    as_bob()
    assert api.get("/api/v1/collection/views").json() == []


def test_cross_user_view_patch_is_404(api):
    view_id = api.post("/api/v1/collection/views",
                       json={"name": "Mine", "filters": {}}).json()["id"]
    as_bob()
    assert api.patch(f"/api/v1/collection/views/{view_id}", json={"name": "Theirs"}) \
        .status_code == 404


def test_cross_user_view_delete_is_404(api):
    view_id = api.post("/api/v1/collection/views",
                       json={"name": "Mine", "filters": {}}).json()["id"]
    as_bob()
    assert api.delete(f"/api/v1/collection/views/{view_id}").status_code == 404


# --- dashboard -----------------------------------------------------------------------

def test_the_dashboard_value_is_null_not_zero(api, catalog):
    add(api, catalog, 1)
    body = api.get("/api/v1/dashboard").json()

    assert body["value"] is None
    assert body["is_empty"] is False
    assert body["total_items"] == 1


def test_an_empty_dashboard_says_so(api, catalog):
    body = api.get("/api/v1/dashboard").json()
    assert body["is_empty"] is True
    assert body["rings"] == []
    assert body["recent"] == []


def test_the_dashboard_ring_agrees_with_the_missing_view(api, catalog):
    """Story 024's last criterion, asserted across the two surfaces that would otherwise
    disagree. Both count distinct cards over the declared printed size."""
    add(api, catalog, 1)
    add(api, catalog, 2)

    ring = api.get("/api/v1/dashboard").json()["rings"][0]
    missing = api.get("/api/v1/collection/missing/FE01").json()

    assert ring["owned_cards"] == missing["owned_cards"]
    assert ring["card_count"] == missing["card_count"]
    assert ring["owned_cards"] + len(missing["missing"]) == ring["card_count"]


def test_cross_user_dashboard_is_empty(api, catalog):
    add(api, catalog, 1)
    as_bob()
    assert api.get("/api/v1/dashboard").json()["is_empty"] is True


# --- history -------------------------------------------------------------------------

def test_history_is_empty_until_the_job_runs(api, catalog):
    add(api, catalog, 1)
    assert api.get("/api/v1/collection/history").json()["items"] == []


def test_history_returns_what_the_job_wrote(api, catalog, db):
    from app.services.snapshot_service import SnapshotService

    add(api, catalog, 1, quantity=3)
    SnapshotService(db).take()

    (row,) = api.get("/api/v1/collection/history").json()["items"]
    assert row["item_count"] == 3
    assert row["total_value_cents"] is None
    assert row["valuation_confidence"] == "none"


def test_cross_user_history_is_empty(api, catalog, db):
    from app.services.snapshot_service import SnapshotService

    add(api, catalog, 1)
    SnapshotService(db).take()

    as_bob()
    assert api.get("/api/v1/collection/history").json()["items"] == []
