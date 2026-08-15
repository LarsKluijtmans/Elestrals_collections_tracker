"""The operator API over import runs — story 009's reporting surface.

`verify_token` is overridden rather than `require_operator`, so the real authorization guard
runs in every test. Overriding the guard itself would test nothing but the override.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.importer.sources import SOURCES, register
from app.importer.sources.csv_seed import CsvSeedAdapter
from app.main import app
from app.repositories.catalog_import_repository import CatalogImportRepository
from app.security import Principal, verify_token

SETS = "set_code,name,series,released_on,card_count\nTT01,Tiny,Testing,,10\n"
CARDS = (
    "set_code,collector_number,name,card_type,element,rune_type,attack,defence,"
    "spirit_cost,rarity,finish,language,edition,image_url\n"
    "TT01,TT-001,Alpha,elestral,fire,,1000,900,,rare,normal,,,\n"
    "TT01,TT-002,Bad,elestral,fire,,1000,900,,not_a_rarity,normal,,,\n"
)


def principal(scope: str) -> Principal:
    return Principal(sub="u-1", project_id="p", company_id="c", email=None,
                     username=None, scope=scope, token_type="access")


@pytest.fixture()
def api(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def operator(api):
    app.dependency_overrides[verify_token] = lambda: principal("elestrals:operator")
    return api


@pytest.fixture()
def civilian(api):
    app.dependency_overrides[verify_token] = lambda: principal("openid profile")
    return api


@pytest.fixture()
def seeded_run(db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.import_runner.log_event", lambda *a, **k: None)
    (tmp_path / "sets.csv").write_text(SETS, encoding="utf-8")
    (tmp_path / "TT01.csv").write_text(CARDS, encoding="utf-8")

    class _Seed(CsvSeedAdapter):
        name = "api_test_seed"

    register(_Seed(tmp_path))
    try:
        from app.core.dependencies import make_import_runner
        yield make_import_runner(db).run(source_name="api_test_seed", set_codes=["TT01"])
    finally:
        SOURCES.pop("api_test_seed", None)


def test_non_operator_is_refused(civilian):
    """403 with no body detail — never a 200 with the interesting fields filtered out."""
    response = civilian.get("/api/v1/admin/catalog/imports")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_operator_lists_runs(operator, seeded_run):
    response = operator.get("/api/v1/admin/catalog/imports")
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 1
    (item,) = body["items"]
    assert item["id"] == seeded_run.id
    assert item["status"] == "success"
    assert item["counts"]["cards_added"] == 1
    assert item["counts"]["rejected"] == 1


def test_run_detail_carries_coverage_and_rejections(operator, seeded_run):
    response = operator.get(f"/api/v1/admin/catalog/imports/{seeded_run.id}")
    assert response.status_code == 200
    body = response.json()

    # Coverage is on the response so bolt 003's console builds a panel, not a query.
    (coverage,) = body["coverage"]
    assert coverage["set_code"] == "TT01"
    assert coverage["expected"] == 10
    assert coverage["imported"] == 1
    assert coverage["missing_count"] == 9

    assert body["rejections"]["total"] == 1
    (rejection,) = body["rejections"]["items"]
    assert rejection["reason_code"] == "unknown_rarity"
    assert rejection["raw_record"]["name"] == "Bad"


def test_unknown_run_is_404_with_a_stable_code(operator):
    response = operator.get("/api/v1/admin/catalog/imports/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "import_run_not_found"


def test_unknown_source_is_rejected_on_start(operator):
    response = operator.post("/api/v1/admin/catalog/imports", json={"source": "nope"})
    assert response.status_code == 404


def test_start_returns_202_with_the_run_id(operator, db, monkeypatch):
    # The endpoint's contract is "row created, id returned, work handed off". Running the
    # real background import here would test `ImportRunner` again — it has its own suite —
    # on a session this test does not own.
    handed_off: list[tuple] = []
    monkeypatch.setattr(
        "app.controllers.admin_catalog._execute",
        lambda *args: handed_off.append(args),
    )

    response = operator.post(
        "/api/v1/admin/catalog/imports", json={"source": "csv_seed", "set_codes": ["FE01"]}
    )
    assert response.status_code == 202

    body = response.json()
    assert body["status"] in ("running", "success")
    assert response.headers["Location"].endswith(body["id"])
    assert CatalogImportRepository(db).get(body["id"]) is not None
    assert handed_off == [(body["id"], "csv_seed", ["FE01"])]


def test_malformed_cursor_is_a_400_not_a_500(operator, seeded_run):
    response = operator.get("/api/v1/admin/catalog/imports?cursor=!!!not-base64!!!")
    assert response.status_code == 400
