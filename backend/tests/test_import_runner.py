"""End-to-end: fetch → normalise → upsert → report, over a real seed on disk.

This is the test that proves the bolt's headline criterion as a whole pipeline rather than
one service in isolation: a second run over an unchanged seed writes nothing to `cards` or
`printings`, and says so honestly in its counters.

`log_event` is stubbed because it opens its own MySQL session by design (a log write must not
ride on the request's transaction). Left real, every event here would attempt a connection and
silently swallow the failure — slow, and it would hide the coverage warning we want to assert.
"""
from __future__ import annotations

import pytest
from conftest import count_writes

from app.core.dependencies import make_import_runner
from app.importer.sources import SOURCES, register
from app.importer.sources.csv_seed import CsvSeedAdapter
from app.repositories.card_repository import CardRepository
from app.repositories.catalog_import_repository import CatalogImportRepository
from app.repositories.set_repository import SetRepository

SETS = """set_code,name,series,released_on,card_count
TT01,Tiny Test Set,Testing,2026-01-01,10
"""

# Two good cards (one with two printings) and one row with an unmappable rarity.
CARDS = """set_code,collector_number,name,card_type,element,rune_type,attack,defence,spirit_cost,rarity,finish,language,edition,image_url
TT01,TT-001,Alpha,elestral,fire,,1000,900,"{""fire"": 1}",rare,normal,,,
TT01,TT-001,Alpha,elestral,fire,,1000,900,"{""fire"": 1}",holo_rare,foil,,,
TT01,TT-002,Beta,rune,,invoke,,,,common,normal,,,
TT01,TT-003,Gamma,rune,,invoke,,,,ultra_mega_rare,normal,,,
"""


class _TestSeed(CsvSeedAdapter):
    name = "test_seed"


@pytest.fixture()
def source(tmp_path):
    (tmp_path / "sets.csv").write_text(SETS, encoding="utf-8")
    (tmp_path / "TT01.csv").write_text(CARDS, encoding="utf-8")
    adapter = _TestSeed(tmp_path)
    register(adapter)
    try:
        yield adapter
    finally:
        SOURCES.pop("test_seed", None)


@pytest.fixture()
def events(monkeypatch):
    captured: list[tuple[str, str, dict]] = []

    def fake(level, message, **kwargs):
        captured.append((level, message, kwargs))

    monkeypatch.setattr("app.services.import_runner.log_event", fake)
    return captured


def run_once(db, source, sets=None):
    return make_import_runner(db).run(source_name=source.name, set_codes=sets or ["TT01"])


def test_first_run_imports_and_reports(db, source, events):
    run = run_once(db, source)

    assert run.status == "success"
    assert run.sets_seen == 1
    assert run.cards_added == 2          # Alpha, Beta
    assert run.printings_added == 3      # Alpha x2, Beta x1
    assert run.cards_unchanged == 0
    assert run.rejected == 1             # Gamma's unmappable rarity
    assert run.set_codes == ["TT01"]
    assert run.finished_at is not None


def test_rejected_card_is_reported_whole_with_a_reason(db, source, events):
    run = run_once(db, source)

    rejections = CatalogImportRepository(db).rejections_for(run.id)
    assert len(rejections) == 1
    rejection = rejections[0]
    assert rejection.reason_code == "unknown_rarity"
    assert rejection.field == "rarity"
    assert rejection.source_ref.startswith("TT01.csv:")
    # The operator can see what actually arrived, not just that something failed.
    assert rejection.raw_record["name"] == "Gamma"


def test_rejections_do_not_make_the_run_a_failure(db, source, events):
    """A run's job is to import what it can and report what it could not — that report is
    story 009, not a failure."""
    assert run_once(db, source).status == "success"


def _catalog_writes(statements: list[str]) -> list[str]:
    return [
        s for s in statements
        if any(t in s.lower() for t in ("cards", "printings", "sets"))
        and "catalog_imports" not in s.lower()
    ]


def test_second_run_writes_nothing_to_the_catalog(db, engine, source, events):
    # Measure both runs through the same filter. If the filter matched nothing this test
    # would pass whatever the importer did, so the first run is the control: it must show
    # writes, and only then does an empty second run mean anything.
    with count_writes(engine) as first:
        run_once(db, source)
    assert _catalog_writes(first), "control failed: the first run should write to the catalog"

    with count_writes(engine) as second:
        run = run_once(db, source)

    assert run.cards_added == 0
    assert run.cards_updated == 0
    assert run.cards_unchanged == 2
    assert _catalog_writes(second) == [], (
        f"re-import touched the catalog: {_catalog_writes(second)}"
    )


def test_incomplete_coverage_is_reported_loudly(db, source, events):
    """10 declared, 2 imported. The warning is what stops completion silently reading 100%."""
    run_once(db, source)

    warnings = [e for e in events if e[0] == "warning" and "coverage" in e[1]]
    assert warnings, f"expected a coverage warning, got {[e[1] for e in events]}"

    context = warnings[0][2]["context"]
    assert context["expected"] == 10
    assert context["imported"] == 2
    assert context["missing_count"] == 8


def test_a_declared_set_with_no_card_file_fails_that_set_only(db, source, events, tmp_path):
    (tmp_path / "sets.csv").write_text(
        SETS + "ZZ99,Never Compiled,Testing,,50\n", encoding="utf-8"
    )

    run = make_import_runner(db).run(source_name=source.name, set_codes=["TT01", "ZZ99"])

    assert run.status == "partial"       # one set in, one failed
    assert run.cards_added == 2
    assert "ZZ99" in (run.error_summary or "")


def test_every_set_failing_is_a_failed_run(db, source, events, tmp_path):
    (tmp_path / "sets.csv").write_text(
        "set_code,name,series,released_on,card_count\nZZ99,Never Compiled,Testing,,50\n",
        encoding="utf-8",
    )

    run = make_import_runner(db).run(source_name=source.name, set_codes=["ZZ99"])

    assert run.status == "failed"
    assert run.cards_added == 0


def test_changed_seed_updates_on_the_next_run(db, source, events, tmp_path):
    run_once(db, source)
    (tmp_path / "TT01.csv").write_text(CARDS.replace("Alpha", "Alpha Prime"), encoding="utf-8")

    run = run_once(db, source)

    assert run.cards_updated == 1
    assert run.cards_unchanged == 1

    set_id = SetRepository(db).get_by_code("TT01").id
    stored = CardRepository(db).get_by_natural_key(set_id, "TT-001")
    assert stored.name == "Alpha Prime"
