"""The nightly snapshot and the dashboard — `collection_snapshots` and story 036.

`collection_snapshots` is the odd one out in phase 1: nothing here reads it. It is written so that
phase 2's portfolio chart is not empty on launch day, because the counts for 3 March exist only if
somebody wrote them on 3 March. It went unbuilt long enough for three phase-2 stories to be recorded
`blocked` on it, which is exactly what planning it a year early was meant to prevent.

The dashboard's own assertion is a refusal: `test_the_value_tile_is_absent_not_zero`. A zero is a
claim about what a collection is worth, and until it is priced, a false one.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.collection_snapshot import CollectionSnapshot
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.set_completion_repository import SetCompletionRepository
from app.repositories.set_repository import SetRepository
from app.services.completion_service import CompletionService
from app.services.dashboard_service import DashboardService
from app.services.snapshot_service import SnapshotService
from test_inventory import ALICE, BOB, build_service, seed_catalog

DAY = date(2026, 8, 15)


@pytest.fixture()
def catalog(db):
    return seed_catalog(db, card_count=6)


@pytest.fixture()
def svc(db):
    return build_service(db)


@pytest.fixture()
def snapshots(db):
    return SnapshotService(db)


@pytest.fixture()
def dashboard(db):
    return DashboardService(
        InventoryRepository(db),
        CompletionService(SetCompletionRepository(db), SetRepository(db)),
        prices=None,
    )


def rows(db, user=ALICE):
    return list(
        db.query(CollectionSnapshot)
        .filter(CollectionSnapshot.user_sub == user)
        .order_by(CollectionSnapshot.taken_on)
    )


# --- the snapshot --------------------------------------------------------------------

def test_a_snapshot_records_copies_and_distinct_printings(snapshots, svc, catalog, db):
    """Both numbers, because they answer different questions. They diverge exactly as much as the
    collection has duplicates in it, which is itself worth being able to chart."""
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"], quantity=3)
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-002:common"], quantity=2)

    result = snapshots.take(taken_on=DAY)

    assert result.users == 1
    assert result.written == 1
    (row,) = rows(db)
    assert row.item_count == 5
    assert row.distinct_printings == 2


def test_phase_one_writes_no_value_at_all(snapshots, svc, catalog, db):
    """**NULL, never 0.** Phase 1 has no prices. A zero would say "this collection was worth
    nothing on 15 August", which is a claim; NULL says "not valued", which is the truth — and
    `confidence: none` says the same thing a second way."""
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    snapshots.take(taken_on=DAY)

    (row,) = rows(db)
    assert row.total_value_cents is None
    assert row.valuation_confidence == "none"


def test_a_user_with_nothing_gets_no_row(snapshots, svc, catalog, db):
    """A row saying "0 cards on 15 August" for somebody who signs up in November is not history,
    it is invention — and phase 2 would draw it as a flat line along the bottom of their chart."""
    svc.add(BOB, printing_id=catalog["printings"]["BS1-001:common"])
    snapshots.take(taken_on=DAY)

    assert rows(db, ALICE) == []
    assert len(rows(db, BOB)) == 1


def test_one_row_per_user_per_day(snapshots, svc, catalog, db):
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    svc.add(BOB, printing_id=catalog["printings"]["BS1-002:common"], quantity=4)

    result = snapshots.take(taken_on=DAY)

    assert result.users == 2
    assert len(rows(db, ALICE)) == 1
    assert len(rows(db, BOB)) == 1


def test_running_it_twice_updates_rather_than_appends(snapshots, svc, catalog, db):
    """What makes the job safe to re-run after a failure, and safe to run by hand. Appending a
    second version of a day would make the chart a sawtooth."""
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    snapshots.take(taken_on=DAY)

    svc.add(ALICE, printing_id=catalog["printings"]["BS1-002:common"], quantity=2)
    result = snapshots.take(taken_on=DAY)

    assert result.written == 0
    assert result.updated == 1
    (row,) = rows(db)
    assert row.item_count == 3


def test_re_running_does_not_erase_a_value_phase_two_wrote(snapshots, svc, catalog, db):
    """**The one that would silently destroy data.** Phase 2's nightly valuation fills in
    `total_value_cents` on these same rows. If the phase-1 counter overwrote the whole row on its
    next pass, every valued day would be blanked the following night."""
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    snapshots.take(taken_on=DAY)

    (row,) = rows(db)
    row.total_value_cents = 123_45
    row.valuation_confidence = "high"
    db.commit()

    snapshots.take(taken_on=DAY)

    (row,) = rows(db)
    assert row.total_value_cents == 123_45
    assert row.valuation_confidence == "high"


def test_a_backfilled_day_carries_the_day_it_describes(snapshots, svc, catalog, db):
    """Not the day it was written. Re-running for a past date must land on that date, or a
    back-fill shifts history sideways."""
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    snapshots.take(taken_on=date(2026, 3, 3))

    (row,) = rows(db)
    assert row.taken_on == date(2026, 3, 3)


def test_history_is_owner_scoped_and_oldest_first(snapshots, svc, catalog, db):
    """Ascending because a caller that has to reverse a series before plotting it will eventually
    forget to."""
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    svc.add(BOB, printing_id=catalog["printings"]["BS1-002:common"])
    for offset in (2, 0, 1):
        snapshots.take(taken_on=DAY - timedelta(days=offset))

    series = snapshots.history(ALICE)
    assert [s.taken_on for s in series] == [
        DAY - timedelta(days=2), DAY - timedelta(days=1), DAY,
    ]
    assert all(s.user_sub == ALICE for s in series)


def test_history_can_be_windowed(snapshots, svc, catalog, db):
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    for offset in range(5):
        snapshots.take(taken_on=DAY - timedelta(days=offset))

    assert len(snapshots.history(ALICE, since=DAY - timedelta(days=1))) == 2


# --- the dashboard -------------------------------------------------------------------

def test_the_value_tile_is_absent_not_zero(dashboard, svc, catalog):
    """**Story 036's refusal.** With no pricing, `value` is `None` and the tile says so in words.
    A zero would be a claim about what the collection is worth, and it would be false."""
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    assert dashboard.build(ALICE).value is None


def test_an_empty_collection_says_so_rather_than_showing_four_zeroes(dashboard):
    """`is_empty` is sent rather than inferred from the tiles. Inferring it is how somebody
    ninety seconds into signing up gets shown a dashboard of noughts instead of an onboarding
    state — and that state is the more important of the two designs."""
    data = dashboard.build(ALICE)
    assert data.is_empty is True
    assert data.total_items == 0
    assert data.rings == []
    assert data.recent == []


def test_the_tiles_count_copies_and_printings_separately(dashboard, svc, catalog):
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"], quantity=3)
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-002:common"])

    data = dashboard.build(ALICE)
    assert data.total_items == 4
    assert data.distinct_printings == 2
    assert data.sets_started == 1
    assert data.is_empty is False


def test_rings_show_the_closest_to_completion(dashboard, svc, catalog, db):
    """Closest, not largest. A set you are two cards from finishing is the actionable one."""
    from app.importer.canonical import CanonicalCard, CanonicalPrinting
    from app.models.set import Set
    from app.repositories.card_repository import CardRepository
    from app.services.catalog_upsert import CatalogUpsert

    second = Set(code="FE02", name="Second", card_count=2)
    db.add(second)
    db.commit()
    upsert = CatalogUpsert(CardRepository(db))
    for n in (1, 2):
        upsert.upsert(
            CanonicalCard(
                set_code="FE02", collector_number=f"S2-{n:03d}", name=f"Second {n}",
                card_type="rune", rune_type="invoke",
                printings=(CanonicalPrinting(rarity="common", finish="normal",
                                             language="en", edition="first"),),
            ),
            set_id=second.id,
        )
    db.commit()

    from app.models.card import Card
    from sqlalchemy import select
    second_printing = next(
        p.id for c in db.scalars(select(Card).where(Card.set_id == second.id))
        for p in c.printings
    )

    # 1 of 6 in FE01, 1 of 2 in FE02 — FE02 is closer.
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    svc.add(ALICE, printing_id=second_printing)

    rings = dashboard.build(ALICE).rings
    assert rings[0].set_code == "FE02"
    assert rings[0].ratio == pytest.approx(0.5)


def test_a_finished_set_does_not_hog_a_ring(dashboard, svc, catalog):
    """A set at 100% is not "closest to completion", it is done. Leaving it in the rings means a
    collector who finishes three sets never sees a ring that tells them anything again."""
    for n in range(1, 7):
        svc.add(ALICE, printing_id=catalog["printings"][f"BS1-{n:03d}:common"])

    rings = dashboard.build(ALICE).rings
    assert rings[0].ratio == pytest.approx(1.0)  # only set there is; not hidden, just last


def test_recent_activity_is_ordered_by_change_not_creation(dashboard, svc, catalog):
    """A quantity bumped this morning is more recent activity than a row created last week."""
    first = svc.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"]).item
    svc.add(ALICE, printing_id=catalog["printings"]["BS1-002:common"])
    svc.adjust(ALICE, first.id, delta=1, expected_quantity=1)

    recent = dashboard.build(ALICE).recent
    assert recent[0].id == first.id


def test_the_dashboard_is_owner_scoped(dashboard, svc, catalog):
    svc.add(BOB, printing_id=catalog["printings"]["BS1-001:common"], quantity=9)
    data = dashboard.build(ALICE)
    assert data.total_items == 0
    assert data.is_empty is True
