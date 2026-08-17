"""`python -m app.jobs` — the nightly snapshot's entrypoint.

The CLI is tested rather than assumed because it is the *only* thing that runs the snapshot. There
is no scheduler in this service; a cron line calls this, and if the argument parsing is wrong the
failure mode is a silent permanent gap in phase 2's chart.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from app.jobs.cli import main
from app.models.collection_snapshot import CollectionSnapshot
from app.models.base import utc_today
from test_inventory import ALICE, build_service, seed_catalog


@pytest.fixture()
def wired(engine, monkeypatch, db):
    """Point the CLI's own session factory at the test database.

    `cli.main` opens its own session on purpose — it runs outside FastAPI's DI graph — so this is
    the seam, and testing through it means the tested path is the deployed path.
    """
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    monkeypatch.setattr("app.jobs.cli.SessionLocal", factory)
    return db


@pytest.fixture()
def collection(wired, db):
    catalog = seed_catalog(db, card_count=3)
    build_service(db).add(ALICE, printing_id=catalog["printings"]["BS1-001:common"], quantity=2)
    return catalog


def rows(db):
    return list(db.query(CollectionSnapshot).order_by(CollectionSnapshot.taken_on))


def test_no_arguments_is_a_usage_error_not_a_silent_success(wired, capsys):
    """A cron line with a typo must fail loudly. Exiting 0 having done nothing is how a nightly
    job goes missing for a month."""
    assert main([]) == 2
    assert "nothing to do" in capsys.readouterr().err


def test_snapshot_writes_a_row(collection, db, capsys):
    assert main(["--snapshot"]) == 0

    (row,) = rows(db)
    assert row.item_count == 2
    # UTC, not `date.today()`. The job stamps the UTC day; comparing against the local day
    # made this test fail between local midnight and UTC midnight and pass again by 02:00.
    assert row.taken_on == utc_today()
    assert "1 written" in capsys.readouterr().out


def test_snapshot_is_idempotent(collection, db):
    main(["--snapshot"])
    main(["--snapshot"])
    assert len(rows(db)) == 1


def test_an_empty_install_is_not_an_error(wired, capsys):
    """Failing the cron job because nobody has added a card yet fills an inbox with alerts about
    nothing, and trains whoever reads them to ignore the next one."""
    assert main(["--snapshot"]) == 0
    assert "no user holds anything yet" in capsys.readouterr().out


def test_backfilling_a_specific_day(collection, db):
    assert main(["--snapshot", "--on", "2026-03-03"]) == 0
    (row,) = rows(db)
    assert row.taken_on == date(2026, 3, 3)


def test_a_malformed_date_is_refused(collection):
    assert main(["--snapshot", "--on", "yesterday"]) == 2


def test_a_future_date_is_refused(collection):
    """A snapshot dated tomorrow sits at the end of every chart as a phantom point that nothing
    can ever correct."""
    tomorrow = (utc_today() + timedelta(days=1)).isoformat()
    assert main(["--snapshot", "--on", tomorrow]) == 2


def test_rebuilding_completion(collection, db, capsys):
    from app.repositories.set_completion_repository import SetCompletionRepository
    from app.repositories.set_repository import SetRepository
    from app.services.completion_service import CompletionService

    assert main(["--rebuild-completion", ALICE]) == 0

    completion = CompletionService(SetCompletionRepository(db), SetRepository(db))
    assert completion.view(ALICE)[0].owned_cards == 1
    assert "rebuilt completion" in capsys.readouterr().out
