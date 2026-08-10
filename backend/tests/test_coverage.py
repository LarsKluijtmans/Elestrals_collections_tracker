"""Coverage: the guard against a completion percentage that silently reads 100%."""
from __future__ import annotations

from app.importer.canonical import CanonicalCard, CanonicalPrinting
from app.models.set import Set
from app.repositories.card_repository import CardRepository
from app.repositories.set_repository import SetRepository
from app.services.catalog_upsert import CatalogUpsert
from app.services.coverage_service import CoverageService, _infer_missing


def add_cards(db, set_row, numbers):
    upsert = CatalogUpsert(CardRepository(db))
    for number in numbers:
        upsert.upsert(
            CanonicalCard(
                set_code=set_row.code, collector_number=number, name=f"Card {number}",
                card_type="rune", rune_type="invoke",
                printings=(CanonicalPrinting(rarity="common", finish="normal",
                                             language="en", edition="first"),),
            ),
            set_id=set_row.id,
        )


def test_incomplete_import_is_reported_not_rounded_away(db):
    set_row = Set(code="FE01", name="Base", card_count=126)
    db.add(set_row)
    db.commit()
    add_cards(db, set_row, ["BS1-001", "BS1-002"])

    report = CoverageService(SetRepository(db), CardRepository(db)).coverage("FE01")

    assert report.expected == 126
    assert report.imported == 2
    assert report.missing_count == 124
    assert report.is_complete is False


def test_declared_set_with_no_cards_reports_zero_coverage(db):
    """The state the shipped seed is in: FE01 declared at 126, nothing compiled yet."""
    db.add(Set(code="FE01", name="Base", card_count=126))
    db.commit()

    report = CoverageService(SetRepository(db), CardRepository(db)).coverage("FE01")

    assert (report.imported, report.expected) == (0, 126)
    assert report.is_complete is False
    assert report.missing_numbers == []  # undecidable with nothing imported


def test_complete_set_is_complete(db):
    set_row = Set(code="TT01", name="Tiny", card_count=3)
    db.add(set_row)
    db.commit()
    add_cards(db, set_row, ["TT-001", "TT-002", "TT-003"])

    report = CoverageService(SetRepository(db), CardRepository(db)).coverage("TT01")
    assert report.is_complete is True
    assert report.missing_numbers == []


def test_unknown_set_yields_no_report(db):
    assert CoverageService(SetRepository(db), CardRepository(db)).coverage("NOPE") is None


def test_missing_numbers_are_named_when_numbering_is_unambiguous():
    assert _infer_missing({"BS1-001", "BS1-003"}, 4) == ["BS1-002", "BS1-004"]


def test_missing_numbers_are_empty_when_undecidable():
    # Mixed prefixes — naming gaps would be a guess.
    assert _infer_missing({"BS1-001", "XY-002"}, 4) == []
    # No digits at all.
    assert _infer_missing({"promo"}, 4) == []
    # Numbering runs past the declared size, so the declaration is untrustworthy.
    assert _infer_missing({"BS1-900"}, 4) == []
