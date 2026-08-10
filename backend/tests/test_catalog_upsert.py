"""Idempotency — the bolt criterion that is either true or a lie.

*"Second run over unchanged sources: 0 added, 0 updated."*

These tests assert against the **SQL actually issued**, not against the importer's own
counters. A naive `INSERT ... ON DUPLICATE KEY UPDATE` with `updated_at` in the UPDATE clause
would rewrite every row on every run while the counters happily reported zero — busy and
idempotent at the same time. Counting statements is the only assertion that catches it.
"""
from __future__ import annotations

from conftest import count_writes

from app.importer.canonical import CanonicalCard, CanonicalPrinting
from app.models.set import Set
from app.repositories.card_repository import CardRepository
from app.services.catalog_upsert import ADDED, UNCHANGED, UPDATED, CatalogUpsert


def make_card(**overrides) -> CanonicalCard:
    fields = {
        "set_code": "FE01",
        "collector_number": "BS1-001",
        "name": "Teratlas",
        "card_type": "elestral",
        "element": "earth",
        "attack": 2400,
        "defence": 2100,
        "spirit_cost": {"earth": 2},
        "printings": (
            CanonicalPrinting(rarity="holo_rare", finish="foil", language="en", edition="first"),
        ),
    }
    fields.update(overrides)
    return CanonicalCard(**fields)


def seed_set(db) -> Set:
    row = Set(code="FE01", name="Base", card_count=126)
    db.add(row)
    db.commit()
    return row


def test_first_upsert_adds_card_and_printings(db):
    set_row = seed_set(db)
    upsert = CatalogUpsert(CardRepository(db))

    result = upsert.upsert(make_card(), set_id=set_row.id)

    assert result.outcome == ADDED
    assert result.printings_added == 1
    assert CardRepository(db).count_for_set(set_row.id) == 1


def test_second_upsert_of_identical_content_issues_no_writes(db, engine):
    """The criterion, asserted at the SQL layer."""
    set_row = seed_set(db)
    upsert = CatalogUpsert(CardRepository(db))
    upsert.upsert(make_card(), set_id=set_row.id)

    with count_writes(engine) as statements:
        result = upsert.upsert(make_card(), set_id=set_row.id)

    assert result.outcome == UNCHANGED
    assert result.printings_added == 0
    assert statements == [], f"expected zero writes on re-import, got {statements}"


def test_changed_card_field_updates_and_writes(db, engine):
    set_row = seed_set(db)
    upsert = CatalogUpsert(CardRepository(db))
    upsert.upsert(make_card(), set_id=set_row.id)

    with count_writes(engine) as statements:
        result = upsert.upsert(make_card(attack=2500), set_id=set_row.id)

    assert result.outcome == UPDATED
    assert statements, "a real change must actually write"

    db.expire_all()
    stored = CardRepository(db).get_by_natural_key(set_row.id, "BS1-001")
    assert stored.attack == 2500


def test_new_printing_on_unchanged_card_counts_as_printing_added(db):
    """Per-entity fingerprints exist for exactly this: a new Holo of an otherwise unchanged
    card is the event an operator needs to see."""
    set_row = seed_set(db)
    upsert = CatalogUpsert(CardRepository(db))
    upsert.upsert(make_card(), set_id=set_row.id)

    two_printings = make_card(printings=(
        CanonicalPrinting(rarity="holo_rare", finish="foil", language="en", edition="first"),
        CanonicalPrinting(rarity="rare", finish="normal", language="en", edition="first"),
    ))
    result = upsert.upsert(two_printings, set_id=set_row.id)

    assert result.outcome == UPDATED
    assert result.printings_added == 1
    assert CardRepository(db).count_printings_for_set(set_row.id) == 2


def test_changed_printing_field_updates_that_printing_only(db):
    set_row = seed_set(db)
    upsert = CatalogUpsert(CardRepository(db))
    upsert.upsert(make_card(), set_id=set_row.id)

    changed = make_card(printings=(
        CanonicalPrinting(rarity="holo_rare", finish="foil", language="en", edition="first",
                          image_url="https://example.test/a.png"),
    ))
    result = upsert.upsert(changed, set_id=set_row.id)

    assert result.outcome == UPDATED
    assert result.printings_updated == 1
    assert result.printings_added == 0


def test_printing_absent_from_source_is_not_deleted(db):
    """Inventory rows point at printings. Deleting one because a source went quiet would
    orphan somebody's collection."""
    set_row = seed_set(db)
    upsert = CatalogUpsert(CardRepository(db))
    upsert.upsert(make_card(printings=(
        CanonicalPrinting(rarity="holo_rare", finish="foil", language="en", edition="first"),
        CanonicalPrinting(rarity="rare", finish="normal", language="en", edition="first"),
    )), set_id=set_row.id)

    upsert.upsert(make_card(), set_id=set_row.id)  # source now lists only one

    assert CardRepository(db).count_printings_for_set(set_row.id) == 2


def test_three_runs_are_stable(db, engine):
    set_row = seed_set(db)
    upsert = CatalogUpsert(CardRepository(db))
    upsert.upsert(make_card(), set_id=set_row.id)
    upsert.upsert(make_card(), set_id=set_row.id)

    with count_writes(engine) as statements:
        result = upsert.upsert(make_card(), set_id=set_row.id)

    assert result.outcome == UNCHANGED
    assert statements == []
