"""Catalog health — staleness, coverage shortfalls, rejection rollup (story 034)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.catalog_import import CatalogImport
from app.models.import_rejection import ImportRejection
from app.models.set import Set
from app.repositories.card_repository import CardRepository
from app.repositories.catalog_import_repository import CatalogImportRepository
from app.repositories.set_repository import SetRepository
from app.services.catalog_health_service import CatalogHealthService, classify

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


def test_never_run_is_its_own_state():
    """Returning `fresh` with a null date would read as healthy."""
    assert classify(None).state == "never_run"
    assert classify(None).age_hours is None


def test_staleness_thresholds():
    assert classify(NOW - timedelta(hours=1), now=NOW).state == "fresh"
    assert classify(NOW - timedelta(hours=47), now=NOW).state == "fresh"
    assert classify(NOW - timedelta(hours=49), now=NOW).state == "ageing"
    assert classify(NOW - timedelta(hours=169), now=NOW).state == "stale"


def test_naive_timestamps_are_treated_as_utc():
    """SQLite hands back naive datetimes; treating them as local would shift staleness by
    hours and, near a threshold, flip the reported state."""
    naive = (NOW - timedelta(hours=1)).replace(tzinfo=None)
    assert classify(naive, now=NOW).state == "fresh"


@pytest.fixture()
def health(db):
    return CatalogHealthService(
        CatalogImportRepository(db), SetRepository(db), CardRepository(db)
    )


def test_registered_source_with_no_runs_still_appears(health):
    """The source an operator most needs to see is the one with no rows to be found by."""
    report = health.health()
    names = [s.source for s in report.sources]

    assert "csv_seed" in names
    entry = next(s for s in report.sources if s.source == "csv_seed")
    assert entry.staleness.state == "never_run"
    assert entry.requires_network is False
    assert entry.last_run_id is None


def test_latest_run_per_source_is_reported(db, health):
    older = CatalogImport(source="csv_seed", status="success",
                          started_at=NOW - timedelta(days=2), finished_at=NOW - timedelta(days=2))
    newer = CatalogImport(source="csv_seed", status="partial",
                          started_at=NOW - timedelta(hours=1), finished_at=NOW)
    db.add_all([older, newer])
    db.commit()

    entry = next(s for s in health.health().sources if s.source == "csv_seed")
    assert entry.last_run_id == newer.id
    assert entry.last_status == "partial"


def test_a_failed_latest_run_does_not_count_as_a_success(db, health):
    db.add(CatalogImport(source="csv_seed", status="failed",
                         started_at=NOW - timedelta(hours=1), finished_at=NOW))
    db.commit()

    entry = next(s for s in health.health().sources if s.source == "csv_seed")
    assert entry.staleness.state == "never_run"  # no successful run has ever happened


def test_sets_below_declared_coverage_are_listed(db, health):
    db.add(Set(code="FE01", name="Base", card_count=126))
    db.commit()

    (shortfall,) = health.health().sets_below_coverage
    assert shortfall.set_code == "FE01"
    assert (shortfall.expected, shortfall.imported, shortfall.missing_count) == (126, 0, 126)


def test_a_set_with_no_declared_size_is_not_reported_as_short(db, health):
    db.add(Set(code="XX01", name="Undeclared", card_count=0))
    db.commit()
    assert health.health().sets_below_coverage == []


def test_rejections_are_rolled_up_by_reason(db, health):
    run = CatalogImport(source="csv_seed", status="success",
                        started_at=NOW, finished_at=NOW)
    db.add(run)
    db.commit()
    db.add_all([
        ImportRejection(import_id=run.id, source_ref=f"FE01.csv:{n}", reason_code="unknown_rarity",
                        message="x")
        for n in (10, 11, 12)
    ] + [
        ImportRejection(import_id=run.id, source_ref="FE01.csv:20",
                        reason_code="conflicting_card_fields", message="y")
    ])
    db.commit()

    report = health.health()
    assert report.latest_run_id == run.id
    # Most frequent first — an operator reads "3 × unknown_rarity", not three rows.
    assert [(r.reason_code, r.count) for r in report.rejections] == [
        ("unknown_rarity", 3), ("conflicting_card_fields", 1)
    ]
    assert report.rejections[0].example_source_ref == "FE01.csv:10"
