"""Import and export over HTTP — bolt 008's routes.

The service tests cover the matcher and the transaction; these cover the wire: multipart upload,
streaming download, the content-disposition that makes a browser save rather than render, and one
cross-user test per endpoint.
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
    return seed_catalog(db, card_count=4)


@pytest.fixture()
def api(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[verify_token] = lambda: principal(ALICE)
    yield TestClient(app)
    app.dependency_overrides.clear()


def as_bob():
    app.dependency_overrides[verify_token] = lambda: principal(BOB)


def upload(api, content: str, filename: str = "cards.csv"):
    return api.post(
        "/api/v1/import",
        files={"file": (filename, content.encode("utf-8"), "text/csv")},
    )


def add(api, catalog, n=1, **body):
    return api.post("/api/v1/inventory", json={
        "printing_id": catalog["printings"][f"BS1-{n:03d}:common"], **body,
    }).json()["item"]


# --- export --------------------------------------------------------------------------

def test_exporting_an_empty_collection_is_a_header_only_file(api, catalog):
    response = api.get("/api/v1/export/collection")
    assert response.status_code == 200
    assert response.text.strip() == "﻿printing_id,set_code,collector_number,name,rarity," \
        "finish,language,edition,condition,quantity,is_graded,grader,grade,acquired_on," \
        "acquired_unit_price_cents,acquired_currency,storage_location,notes,is_for_trade"


def test_the_download_is_named_and_attached(api, catalog):
    response = api.get("/api/v1/export/collection")
    # `attachment` so the browser saves rather than rendering CSV as a wall of text in a tab.
    assert "attachment" in response.headers["content-disposition"]
    assert "elestrals-collection.csv" in response.headers["content-disposition"]


def test_the_export_starts_with_a_bom(api, catalog):
    """So Excel reads UTF-8 rather than the system codepage. Without it a card called "Pyrofrost
    Éclair" arrives as mojibake, which reads to the user as our data being wrong."""
    add(api, catalog, 1)
    assert api.get("/api/v1/export/collection").text.startswith("﻿")


def test_the_export_honours_the_active_filter(api, catalog):
    """Story 027, and the reason the query string is passed through verbatim: the link in the
    address bar and the file that comes out describe the same rows."""
    add(api, catalog, 1, condition="damaged")
    add(api, catalog, 2)
    add(api, catalog, 3)

    everything = api.get("/api/v1/export/collection").text
    filtered = api.get("/api/v1/export/collection?request_filters=condition%3Ddamaged").text

    assert len(everything.strip().splitlines()) == 4  # header + 3
    assert len(filtered.strip().splitlines()) == 2    # header + 1


def test_an_invalid_export_filter_is_400(api, catalog):
    assert api.get(
        "/api/v1/export/collection?request_filters=condition%3Dmnt"
    ).status_code == 400


def test_exporting_sealed_and_wishlist(api, catalog):
    for kind in ("sealed", "wishlist"):
        response = api.get(f"/api/v1/export/{kind}")
        assert response.status_code == 200
        assert f"elestrals-{kind}.csv" in response.headers["content-disposition"]


def test_cross_user_export_is_empty(api, catalog):
    add(api, catalog, 1)
    as_bob()
    assert len(api.get("/api/v1/export/collection").text.strip().splitlines()) == 1


# --- import --------------------------------------------------------------------------

def test_uploading_returns_a_dry_run(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    response = upload(api, f"printing_id,quantity\r\n{pid},3\r\n")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ready"
    assert body["add_count"] == 1
    assert body["total_rows"] == 1


def test_the_dry_run_reports_how_the_file_was_read(api, catalog):
    """"We read this as CP1252, semicolon-separated" is a complaint somebody can act on. "The
    preview looks wrong" is not."""
    pid = catalog["printings"]["BS1-001:common"]
    body = upload(api, f"printing_id;quantity\r\n{pid};3\r\n").json()

    assert body["delimiter"] == ";"
    assert body["encoding"].startswith("utf-8")


def test_uploading_writes_nothing_to_the_collection(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    upload(api, f"printing_id,quantity\r\n{pid},5\r\n")

    assert api.get("/api/v1/collection").json()["total"] == 0


def test_a_header_only_file_is_400(api, catalog):
    assert upload(api, "printing_id,quantity\r\n").status_code == 400


def test_an_empty_upload_is_400(api, catalog):
    assert upload(api, "").status_code == 400


def test_rows_needing_attention_come_first(api, catalog):
    """A diff that buries four rejections under four thousand clean rows is a diff nobody reads."""
    pid = catalog["printings"]["BS1-001:common"]
    body = upload(api, "\r\n".join([
        "printing_id,quantity", f"{pid},1", "nonsense,1", f"{pid},1",
    ])).json()

    assert body["rows"][0]["verdict"] == "rejected"


def test_remapping_over_http_reruns_the_dry_run(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    job = upload(api, f"thing,howmany\r\n{pid},2\r\n").json()
    assert job["rejected_count"] == 1

    remapped = api.put(f"/api/v1/import/{job['id']}/mapping", json={
        "mapping": {"printing_id": "thing", "quantity": "howmany"},
    }).json()
    assert remapped["add_count"] == 1


def test_committing_applies_the_import(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    job = upload(api, f"printing_id,quantity\r\n{pid},3\r\n").json()

    result = api.post(f"/api/v1/import/{job['id']}/commit").json()

    assert result == {"added": 1, "updated": 0, "skipped": 0, "rows": 1}
    assert api.get("/api/v1/collection").json()["items"][0]["quantity"] == 3


def test_committing_twice_is_409(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    job = upload(api, f"printing_id\r\n{pid}\r\n").json()
    api.post(f"/api/v1/import/{job['id']}/commit")

    assert api.post(f"/api/v1/import/{job['id']}/commit").status_code == 409


def test_confirming_a_fuzzy_row_over_http(api, catalog):
    job = upload(api, "name,set_code\r\nCard 1 (Holo),FE01\r\n").json()
    assert job["needs_confirmation_count"] == 1

    row_id = job["rows"][0]["id"]
    confirmed = api.post(f"/api/v1/import/{job['id']}/confirm",
                         json={"row_ids": [row_id]}).json()
    assert confirmed["rows"][0]["confirmed"] is True

    result = api.post(f"/api/v1/import/{job['id']}/commit").json()
    assert result["added"] == 1


def test_an_unconfirmed_fuzzy_row_is_skipped_not_imported(api, catalog):
    """Rung 4 never applies on its own. That is the line the whole ladder exists to hold."""
    job = upload(api, "name,set_code\r\nCard 1 (Holo),FE01\r\n").json()
    result = api.post(f"/api/v1/import/{job['id']}/commit").json()

    assert result["added"] == 0
    assert result["skipped"] == 1


def test_listing_jobs_omits_the_rows(api, catalog):
    # A list endpoint returning every row of every job is a payload nobody asked for.
    pid = catalog["printings"]["BS1-001:common"]
    upload(api, f"printing_id\r\n{pid}\r\n")

    listed = api.get("/api/v1/import").json()
    assert len(listed) == 1
    assert listed[0]["rows"] == []


def test_a_job_can_be_fetched_again_later(api, catalog):
    """Story 028: leaving the page must not lose the job."""
    pid = catalog["printings"]["BS1-001:common"]
    job = upload(api, f"printing_id\r\n{pid}\r\n").json()

    again = api.get(f"/api/v1/import/{job['id']}").json()
    assert again["status"] == "ready"
    assert len(again["rows"]) == 1


def test_deleting_a_job(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    job = upload(api, f"printing_id\r\n{pid}\r\n").json()

    assert api.delete(f"/api/v1/import/{job['id']}").status_code == 204
    assert api.get(f"/api/v1/import/{job['id']}").status_code == 404


# --- cross-user ----------------------------------------------------------------------

def test_cross_user_job_fetch_is_404(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    job = upload(api, f"printing_id\r\n{pid}\r\n").json()
    as_bob()
    assert api.get(f"/api/v1/import/{job['id']}").status_code == 404


def test_cross_user_remap_is_404(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    job = upload(api, f"printing_id\r\n{pid}\r\n").json()
    as_bob()
    assert api.put(f"/api/v1/import/{job['id']}/mapping",
                   json={"mapping": {}}).status_code == 404


def test_cross_user_confirm_is_404(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    job = upload(api, f"printing_id\r\n{pid}\r\n").json()
    as_bob()
    assert api.post(f"/api/v1/import/{job['id']}/confirm",
                    json={"row_ids": []}).status_code == 404


def test_cross_user_commit_is_404(api, catalog):
    """The one that would let a stranger write into someone else's collection."""
    pid = catalog["printings"]["BS1-001:common"]
    job = upload(api, f"printing_id\r\n{pid}\r\n").json()
    as_bob()
    assert api.post(f"/api/v1/import/{job['id']}/commit").status_code == 404


def test_cross_user_delete_is_404(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    job = upload(api, f"printing_id\r\n{pid}\r\n").json()
    as_bob()
    assert api.delete(f"/api/v1/import/{job['id']}").status_code == 404


def test_cross_user_job_list_is_empty(api, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    upload(api, f"printing_id\r\n{pid}\r\n")
    as_bob()
    assert api.get("/api/v1/import").json() == []


# --- the round trip, end to end ------------------------------------------------------

def test_export_then_import_over_http_changes_nothing(api, catalog):
    """The bolt's headline criterion, through the actual endpoints: 0 adds, 0 rejects."""
    add(api, catalog, 1, quantity=3)
    add(api, catalog, 2, condition="damaged")

    exported = api.get("/api/v1/export/collection").text
    job = upload(api, exported, filename="round-trip.csv").json()

    assert job["rejected_count"] == 0
    assert job["add_count"] == 0
    assert job["update_count"] == 2
    assert all(r["match_rung"] == "exact_printing" for r in job["rows"])
