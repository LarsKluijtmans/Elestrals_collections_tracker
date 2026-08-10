"""The public catalog surface.

No `verify_token` override anywhere in this file, on purpose: these routes must work with no
Authorization header at all. If one ever gained an authenticated dependency, every test here
would start failing with a 401 rather than silently becoming user-specific behind a shared
cache.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.importer.canonical import CanonicalCard, CanonicalPrinting
from app.main import app
from app.models.set import Set
from app.repositories.card_repository import CardRepository
from app.services.catalog_upsert import CatalogUpsert


@pytest.fixture()
def api(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def catalog(db):
    set_row = Set(code="FE01", name="Base", card_count=10, series="First Edition")
    db.add(set_row)
    db.commit()

    CatalogUpsert(CardRepository(db)).upsert(
        CanonicalCard(
            set_code="FE01", collector_number="BS1-001", name="Teratlas",
            card_type="elestral", element="earth", attack=2400, defence=2100,
            spirit_cost={"earth": 2},
            printings=(
                CanonicalPrinting(rarity="rare", finish="normal", language="en",
                                  edition="first"),
                CanonicalPrinting(rarity="holo_rare", finish="foil", language="en",
                                  edition="first"),
            ),
        ),
        set_id=set_row.id,
    )
    return set_row


def test_search_works_signed_out(api, catalog):
    response = api.get("/api/v1/cards", params={"q": "tera"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Teratlas"
    assert body["items"][0]["match_kind"] == "name_prefix"


def test_public_responses_are_cacheable_and_do_not_vary_on_the_caller(api, catalog):
    """The cache header is only sound because nothing here is user-specific."""
    for path in ("/api/v1/cards?q=tera", "/api/v1/sets", "/api/v1/sets/FE01"):
        response = api.get(path)
        assert response.status_code == 200, path
        assert "public" in response.headers["cache-control"], path
        assert "authorization" not in response.headers.get("vary", "").lower(), path


def test_short_query_is_an_empty_200_not_an_error(api, catalog):
    response = api.get("/api/v1/cards", params={"q": "t"})
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None, "total": 0}


def test_primary_printing_is_the_commonest(api, catalog):
    (item,) = api.get("/api/v1/cards", params={"q": "tera"}).json()["items"]
    assert item["printing_count"] == 2
    assert item["primary_printing"]["rarity"] == "rare"
    assert item["primary_printing"]["alt_text"] == "Teratlas — FE01 rare"


def test_card_detail_lists_every_printing(api, catalog, db):
    card_id = api.get("/api/v1/cards", params={"q": "tera"}).json()["items"][0]["card_id"]

    body = api.get(f"/api/v1/cards/{card_id}").json()
    assert body["name"] == "Teratlas"
    assert body["set_name"] == "Base"
    assert body["spirit_cost"] == {"earth": 2}
    assert [p["rarity"] for p in body["printings"]] == ["rare", "holo_rare"]
    assert body["printings"][0]["alt_text"] == "Teratlas — FE01 rare"


def test_unknown_card_is_404_with_a_stable_code(api, catalog):
    response = api.get("/api/v1/cards/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "card_not_found"


def test_set_gallery_reports_declared_and_imported_counts(api, catalog):
    (item,) = api.get("/api/v1/sets").json()["items"]
    assert item["code"] == "FE01"
    assert item["card_count"] == 10      # declared printed size
    assert item["imported_count"] == 1   # what we actually hold


def test_set_summary_has_no_user_specific_field(api, catalog):
    """Completion is per-user and lives on bolt 004's endpoint. If it ever appears here, the
    shared cache would serve one collector's data to another."""
    (item,) = api.get("/api/v1/sets").json()["items"]
    assert "completion" not in item
    assert "owned" not in item


def test_set_checklist(api, catalog):
    body = api.get("/api/v1/sets/FE01").json()
    assert body["set"]["code"] == "FE01"
    assert body["total"] == 1
    (entry,) = body["items"]
    assert entry["collector_number"] == "BS1-001"
    assert len(entry["printings"]) == 2


def test_unknown_set_is_404(api, catalog):
    response = api.get("/api/v1/sets/ZZ99")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "set_not_found"


def test_series_filter(api, catalog):
    assert api.get("/api/v1/sets", params={"series": "First Edition"}).json()["items"]
    assert api.get("/api/v1/sets", params={"series": "Nope"}).json()["items"] == []


def test_malformed_cursor_is_a_400(api, catalog):
    assert api.get("/api/v1/cards?q=tera&cursor=!!!").status_code == 400
    assert api.get("/api/v1/sets/FE01?cursor=!!!").status_code == 400


def test_filters_use_or_within_and_across_attributes(api, catalog):
    # element=earth OR fire -> matches; card_type=rune -> excludes.
    hit = api.get("/api/v1/cards", params=[("q", "tera"), ("element", "earth"),
                                           ("element", "fire")]).json()
    assert hit["total"] == 1

    miss = api.get("/api/v1/cards", params=[("q", "tera"), ("element", "earth"),
                                            ("card_type", "rune")]).json()
    assert miss["total"] == 0
