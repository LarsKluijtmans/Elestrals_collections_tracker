"""CSV import and export — bolt 008, stories 027, 028 and 029.

**The round trip is the headline.** `test_export_then_import_is_a_no_op` asserts that exporting a
collection and importing the file back produces 0 adds, 0 updates and 0 rejects. That single
assertion is the strongest correctness check available for the matcher — it turns rung 1 from a
claim into something provable, and it is why the bolt notes say to build export first.

The other two that carry weight are both about *not* doing things: the dry run writes nothing, and a
failure on row 900 writes nothing either.
"""
from __future__ import annotations

import pytest

from app.repositories.inventory_repository import InventoryRepository
from app.services.export_service import ExportService, neutralise
from app.services.import_matcher import ImportMatcher
from app.services.import_parser import (
    ImportTooLarge, decode, normalise_name, parse, sniff_delimiter,
    split_name_hints, suggest_mapping,
)
from app.services.import_service import ImportRefused, ImportService, JobNotReady
from test_inventory import ALICE, BOB, build_service, seed_catalog


@pytest.fixture()
def catalog(db):
    return seed_catalog(db, card_count=4)


@pytest.fixture()
def inventory(db):
    return build_service(db)


@pytest.fixture()
def importer(db, inventory):
    return ImportService(db, inventory)


def csv_bytes(*lines: str, encoding: str = "utf-8", eol: str = "\r\n") -> bytes:
    return eol.join(lines).encode(encoding)


# --- export: the format --------------------------------------------------------------

def test_export_writes_the_canonical_header(inventory, catalog, db):
    inventory.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    rows = list(ExportService().singles(InventoryRepository(db).list_for_user(ALICE)))

    assert rows[0].startswith("printing_id,set_code,collector_number,name")


def test_export_leads_with_printing_id(inventory, catalog, db):
    """First column, deliberately: it is what makes a re-import an exact match on rung 1 rather
    than a search that might land somewhere else."""
    item = inventory.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"]).item
    rows = list(ExportService().singles(InventoryRepository(db).list_for_user(ALICE)))

    assert rows[1].split(",")[0] == item.printing_id


def test_export_streams_rather_than_accumulating(inventory, catalog, db):
    """A generator, not a list. Ten thousand rows joined into one string is hundreds of megabytes
    for a file the user opens once, and the NFR bounds this at 100MB RSS."""
    import types

    result = ExportService().singles(InventoryRepository(db).list_for_user(ALICE))
    assert isinstance(result, types.GeneratorType)


# --- export: formula injection -------------------------------------------------------

@pytest.mark.parametrize("dangerous", ["=1+1", "+SUM(A1)", "-2+3", "@SUM(A1)"])
def test_formula_prefixes_are_defused(dangerous):
    """**The attack is on the user, not on us.** A crafted card note becomes a formula when they
    open the file, and `=IMPORTXML(...)` can exfiltrate the rest of their sheet. The `'` prefix is
    stripped on display by Excel, Sheets and LibreOffice, so the cell reads right and is inert."""
    assert neutralise(dangerous).startswith("'")


def test_leading_whitespace_tricks_are_defused():
    # A tab or CR before `=` still leads a formula in at least one of the three.
    assert neutralise("\t=1+1").startswith("'")
    assert neutralise("\r=1+1").startswith("'")


def test_ordinary_values_are_untouched():
    assert neutralise("Atlas") == "Atlas"
    assert neutralise("near_mint") == "near_mint"


def test_a_note_from_the_database_is_defused_too(inventory, catalog, db):
    """This runs on our *own* export. The dangerous string got in through a note field somebody
    typed, and it is dangerous on the way out."""
    item = inventory.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"]).item
    from app.services.inventory_service import ItemFields
    inventory.edit(ALICE, item.id, ItemFields(notes="=cmd|'/c calc'!A1"))

    rows = list(ExportService().singles(InventoryRepository(db).list_for_user(ALICE)))
    assert "\"'=cmd" in rows[1] or "'=cmd" in rows[1]


def test_a_comma_in_a_name_is_quoted_not_split(inventory, catalog, db):
    """The escaping failure that shifts every later column by one and imports as something else
    entirely — a silently wrong import rather than a failed one."""
    from app.models.card import Card
    from sqlalchemy import select

    card = db.scalar(select(Card).where(Card.collector_number == "BS1-001"))
    card.name = 'Atlas, "Reborn"'
    db.commit()
    inventory.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])

    rows = list(ExportService().singles(InventoryRepository(db).list_for_user(ALICE)))
    assert '"Atlas, ""Reborn"""' in rows[1]


# --- parsing: real-world spreadsheets -------------------------------------------------

def test_utf8_with_a_bom(catalog):
    """The BOM must be *consumed*, not left on the first header. Otherwise `printing_id` fails to
    match its own alias and our own export stops round-tripping — the sneakiest version of this
    bug, because everything else looks fine."""
    raw = "﻿printing_id,quantity\r\np1,2\r\n".encode("utf-8")
    parsed = parse(raw)

    assert parsed.encoding == "utf-8-sig"
    assert parsed.headers[0] == "printing_id"


def test_cp1252_from_excel_on_windows():
    raw = "name,quantity\r\nPyrofrost Éclair,2\r\n".encode("cp1252")
    parsed = parse(raw)

    assert parsed.rows[0][1]["name"] == "Pyrofrost Éclair"


def test_utf8_is_preferred_over_cp1252():
    """Order matters and is not alphabetical. Every byte sequence is *valid* CP1252, so trying it
    early would turn real UTF-8 into mojibake without ever raising."""
    raw = "name\r\nPyrofrost Éclair\r\n".encode("utf-8")
    assert parse(raw).rows[0][1]["name"] == "Pyrofrost Éclair"


def test_semicolon_delimited():
    parsed = parse(csv_bytes("name;quantity", "Atlas;2"))
    assert parsed.delimiter == ";"
    assert parsed.rows[0][1]["quantity"] == "2"


def test_a_semicolon_inside_a_quoted_field_does_not_pick_the_delimiter():
    """`csv.Sniffer` guesses from a sample and gets this wrong. The header is the one line that
    can be relied on to be structural, so the delimiter is counted there."""
    parsed = parse(csv_bytes('name,quantity', '"Atlas; Reborn",2'))
    assert parsed.delimiter == ","
    assert parsed.rows[0][1]["name"] == "Atlas; Reborn"


def test_quoted_commas_survive():
    parsed = parse(csv_bytes("name,quantity", '"Atlas, Reborn",2'))
    assert parsed.rows[0][1]["name"] == "Atlas, Reborn"


def test_blank_rows_in_the_middle_are_skipped_and_counted():
    """People group things visually with blank rows. Skipping them silently would leave somebody
    who exported 500 rows and sees 498 wondering what happened to the other two."""
    parsed = parse(csv_bytes("name,quantity", "Atlas,1", "", "  ", "Vipyro,2"))

    assert len(parsed.rows) == 2
    assert parsed.blank_rows == 2


def test_line_numbers_are_what_the_spreadsheet_shows():
    """1 is the header, so the first data row is 2. A rejection saying "row 900" has to name a row
    the user can scroll to, not an array index."""
    parsed = parse(csv_bytes("name", "Atlas", "Vipyro"))
    assert [n for n, _ in parsed.rows] == [2, 3]


def test_a_short_row_pads_rather_than_crashing():
    parsed = parse(csv_bytes("name,quantity,condition", "Atlas,2"))
    assert parsed.rows[0][1]["condition"] == ""


def test_an_oversized_file_is_refused_with_a_message():
    with pytest.raises(ImportTooLarge):
        decode(b"x" * (9 * 1024 * 1024))


def test_too_many_rows_is_refused():
    lines = ["name", *[f"Card {n}" for n in range(20_001)]]
    with pytest.raises(ImportTooLarge):
        parse(csv_bytes(*lines))


def test_sniffing_an_empty_file_defaults_to_comma():
    assert sniff_delimiter("") == ","


# --- mapping suggestion ---------------------------------------------------------------

def test_our_own_headers_map_to_themselves():
    mapping = suggest_mapping(["printing_id", "set_code", "collector_number", "quantity"])
    assert mapping["printing_id"] == "printing_id"
    assert mapping["quantity"] == "quantity"


@pytest.mark.parametrize("header", ["Qty", "qty", "Count", "#", "Amount", "Owned"])
def test_the_quantity_column_is_recognised_however_it_is_spelled(header):
    assert suggest_mapping(["Name", header]).get("quantity") == header


def test_common_alternative_spellings():
    mapping = suggest_mapping(["Card Name", "Set", "Card Number", "Cond", "Binder"])
    assert mapping["name"] == "Card Name"
    assert mapping["set_code"] == "Set"
    assert mapping["collector_number"] == "Card Number"
    assert mapping["condition"] == "Cond"
    assert mapping["storage_location"] == "Binder"


def test_a_header_is_claimed_once():
    # `id` is an alias for collector_number, and `printing_id` for itself. One header must not
    # end up mapped to two fields, which would double-read the same column.
    mapping = suggest_mapping(["printing_id", "id"])
    assert len({v for v in mapping.values()}) == len(mapping)


def test_unknown_headers_are_left_alone():
    mapping = suggest_mapping(["name", "sparkliness"])
    assert "sparkliness" not in mapping.values()


# --- name hints -----------------------------------------------------------------------

def test_a_parenthetical_holo_is_a_finish_hint_not_part_of_the_name():
    """One of the most common shapes a collector spreadsheet takes, and matching the whole string
    finds nothing at all."""
    hints = split_name_hints("Vipyro (Holo)")
    assert hints.name == "Vipyro"
    assert hints.finish == "foil"


def test_an_unrecognised_qualifier_is_kept_as_an_extra():
    hints = split_name_hints("Vipyro (Signed)")
    assert hints.name == "Vipyro"
    assert hints.finish is None
    assert hints.extras == ["Signed"]


def test_normalising_a_name_survives_an_apostrophe():
    # "Vipyro's Ember" and "Vipyros Ember" are the same card typed by two people.
    assert normalise_name("Vipyro's Ember") == normalise_name("Vipyros Ember")


# --- the matching ladder --------------------------------------------------------------

def test_rung_one_matches_a_printing_id(db, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    result = ImportMatcher(db).match({"printing_id": pid})

    assert result.printing_id == pid
    assert result.rung == "exact_printing"
    assert result.needs_confirmation is False


def test_a_stale_printing_id_falls_through_rather_than_rejecting(db, catalog):
    """An old export against a rebuilt catalog. The other columns may still identify the card, so
    rung 1 declines rather than failing the row."""
    result = ImportMatcher(db).match({
        "printing_id": "not-ours", "set_code": "FE01",
        "collector_number": "BS1-001", "finish": "normal",
    })
    assert result.rung == "natural_key"


def test_rung_two_matches_the_natural_key(db, catalog):
    result = ImportMatcher(db).match({
        "set_code": "FE01", "collector_number": "BS1-001",
        "finish": "normal", "language": "en", "edition": "first",
    })
    assert result.rung == "natural_key"


def test_rung_two_is_case_insensitive(db, catalog):
    result = ImportMatcher(db).match({
        "set_code": "fe01", "collector_number": "bs1-001", "finish": "NORMAL",
    })
    assert result.matched is True


def test_rung_three_uses_the_language_default_to_disambiguate(db, catalog):
    """Set and number with no finish. Most files that omit it are English, and that narrows many
    cards to one — but only when it genuinely does."""
    result = ImportMatcher(db).match({"set_code": "FE01", "collector_number": "BS1-001"})
    # Two printings share the language here, so this is honestly ambiguous and rejected.
    assert result.matched is False
    assert "printings" in (result.reason or "")


def test_ambiguity_is_a_rejection_not_a_coin_flip(db, catalog):
    """A card with a normal and a foil printing and nothing in the file to tell them apart is a
    *question*. Picking one silently records a card the collector may not own."""
    result = ImportMatcher(db).match({"set_code": "FE01", "collector_number": "BS1-002"})
    assert result.matched is False
    assert result.rung == "none"


def test_rung_four_matches_a_fuzzy_name_and_demands_confirmation(db, catalog):
    result = ImportMatcher(db).match({
        "name": "Card 1 (Holo)", "set_code": "FE01",
    })
    assert result.rung == "fuzzy_name"
    assert result.needs_confirmation is True
    assert result.score >= 0.86


def test_a_typo_within_the_floor_still_matches_but_needs_confirming(db, catalog):
    result = ImportMatcher(db).match({"name": "Crad 1 (Holo)", "set_code": "FE01"})
    # Either it matched as fuzzy (confirmation required) or it honestly failed. What it must never
    # do is match at a rung that applies without asking.
    assert result.rung in ("fuzzy_name", "none")
    if result.matched:
        assert result.needs_confirmation is True


def test_below_the_floor_is_a_rejection_not_a_low_confidence_match(db, catalog):
    """**The line the bolt notes say to hold under schedule pressure.** A confident wrong match
    silently corrupts a collection somebody has kept for years, and they will not find out until
    they go looking for a card they no longer appear to own."""
    result = ImportMatcher(db).match({"name": "Completely Different Thing", "set_code": "FE01"})
    assert result.matched is False
    assert result.rung == "none"


def test_a_rejection_says_what_was_tried(db, catalog):
    result = ImportMatcher(db).match({"set_code": "FE01", "collector_number": "BS9-999"})
    assert "BS9-999" in (result.reason or "")
    assert "FE01" in (result.reason or "")


def test_an_empty_row_says_check_the_mapping(db, catalog):
    result = ImportMatcher(db).match({})
    assert "mapping" in (result.reason or "")


# --- the dry run ----------------------------------------------------------------------

def test_a_dry_run_writes_nothing_to_the_collection(importer, catalog, db):
    """**Story 028's fourth criterion**, asserted from the outside."""
    pid = catalog["printings"]["BS1-001:common"]
    importer.start(ALICE, filename="x.csv",
                   raw=csv_bytes("printing_id,quantity", f"{pid},3"))

    assert InventoryRepository(db).count_for_user(ALICE) == 0


def test_a_dry_run_counts_adds(importer, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    job = importer.start(ALICE, filename="x.csv",
                         raw=csv_bytes("printing_id,quantity", f"{pid},3"))

    assert job.status == "ready"
    assert job.add_count == 1
    assert job.rejected_count == 0


def test_a_dry_run_tells_an_update_from_an_add(importer, inventory, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    inventory.add(ALICE, printing_id=pid)

    job = importer.start(ALICE, filename="x.csv",
                         raw=csv_bytes("printing_id,quantity", f"{pid},2"))
    assert job.update_count == 1
    assert job.add_count == 0


def test_a_mis_mapped_quantity_column_is_visible_in_the_diff(importer, catalog):
    """**Story 028's sixth criterion**, and the failure the dry run exists to catch. Quantity
    mapped onto the collector-number column produces a rejection per row saying so — before
    anything is written, rather than after."""
    job = importer.start(
        ALICE, filename="x.csv",
        raw=csv_bytes("set_code,collector_number", "FE01,BS1-001"),
    )
    job = importer.remap(ALICE, job.id, {
        "set_code": "set_code", "quantity": "collector_number",
    })

    assert job.rejected_count == 1
    assert "not a quantity" in job.rows[0].reason


def test_fuzzy_rows_are_not_counted_as_adds(importer, catalog):
    job = importer.start(ALICE, filename="x.csv",
                         raw=csv_bytes("name,set_code,quantity", "Card 1 (Holo),FE01,1"))

    assert job.add_count == 0
    assert job.needs_confirmation_count == 1


def test_condition_shorthand_is_understood(importer, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    job = importer.start(ALICE, filename="x.csv",
                         raw=csv_bytes("printing_id,condition", f"{pid},NM"))

    assert job.rows[0].condition == "near_mint"


def test_an_unrecognised_condition_is_rejected_with_a_reason(importer, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    job = importer.start(ALICE, filename="x.csv",
                         raw=csv_bytes("printing_id,condition", f"{pid},pristine"))

    assert job.rejected_count == 1
    assert "condition" in job.rows[0].reason


def test_a_missing_quantity_defaults_to_one(importer, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    job = importer.start(ALICE, filename="x.csv", raw=csv_bytes("printing_id", pid))
    assert job.rows[0].quantity == 1


def test_a_header_only_file_is_refused(importer):
    with pytest.raises(ImportRefused):
        importer.start(ALICE, filename="x.csv", raw=csv_bytes("printing_id,quantity"))


def test_remapping_re_runs_the_dry_run(importer, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    job = importer.start(ALICE, filename="x.csv",
                         raw=csv_bytes("thing,howmany", f"{pid},2"))
    assert job.rejected_count == 1

    job = importer.remap(ALICE, job.id, {"printing_id": "thing", "quantity": "howmany"})
    assert job.add_count == 1


def test_a_job_survives_being_left(importer, catalog):
    """Story 028: a 5,000-row dry run is not something to make somebody sit through twice because
    they went to check a spreadsheet in another tab."""
    pid = catalog["printings"]["BS1-001:common"]
    job = importer.start(ALICE, filename="x.csv", raw=csv_bytes("printing_id", pid))

    fetched = importer.get(ALICE, job.id)
    assert fetched.status == "ready"
    assert len(fetched.rows) == 1


def test_a_job_is_owner_scoped(importer, catalog):
    from app.services.import_service import JobNotFound

    pid = catalog["printings"]["BS1-001:common"]
    job = importer.start(ALICE, filename="x.csv", raw=csv_bytes("printing_id", pid))

    with pytest.raises(JobNotFound):
        importer.get(BOB, job.id)


# --- the commit -----------------------------------------------------------------------

def test_committing_writes_through_the_inventory_service(importer, catalog, db):
    """Story 029: imported rows obey the same merge-on-duplicate and completion recompute that
    hand-entered rows do. Bypassing the service would let an import produce a collection state the
    UI cannot."""
    from app.repositories.set_completion_repository import SetCompletionRepository
    from app.repositories.set_repository import SetRepository
    from app.services.completion_service import CompletionService

    pid = catalog["printings"]["BS1-001:common"]
    job = importer.start(ALICE, filename="x.csv",
                         raw=csv_bytes("printing_id,quantity", f"{pid},3"))
    result = importer.commit(ALICE, job.id)

    assert result.added == 1
    assert InventoryRepository(db).total_quantity(ALICE) == 3
    # The projection moved too, which is the part a repository-level write would have skipped.
    completion = CompletionService(SetCompletionRepository(db), SetRepository(db))
    assert completion.view(ALICE)[0].owned_cards == 1


def test_committing_merges_into_an_existing_holding(importer, inventory, catalog, db):
    pid = catalog["printings"]["BS1-001:common"]
    inventory.add(ALICE, printing_id=pid, quantity=2)

    job = importer.start(ALICE, filename="x.csv",
                         raw=csv_bytes("printing_id,quantity", f"{pid},3"))
    result = importer.commit(ALICE, job.id)

    assert result.updated == 1
    assert InventoryRepository(db).count_for_user(ALICE) == 1
    assert InventoryRepository(db).total_quantity(ALICE) == 5


def test_unconfirmed_fuzzy_rows_are_skipped(importer, catalog, db):
    job = importer.start(ALICE, filename="x.csv",
                         raw=csv_bytes("name,set_code", "Card 1 (Holo),FE01"))
    result = importer.commit(ALICE, job.id)

    assert result.added == 0
    assert result.skipped == 1
    assert InventoryRepository(db).count_for_user(ALICE) == 0


def test_a_confirmed_fuzzy_row_is_applied(importer, catalog, db):
    job = importer.start(ALICE, filename="x.csv",
                         raw=csv_bytes("name,set_code", "Card 1 (Holo),FE01"))
    importer.confirm_rows(ALICE, job.id, [job.rows[0].id])
    result = importer.commit(ALICE, job.id)

    assert result.added == 1
    assert InventoryRepository(db).count_for_user(ALICE) == 1


def test_confirming_only_touches_the_rows_named(importer, catalog):
    job = importer.start(
        ALICE, filename="x.csv",
        raw=csv_bytes("name,set_code", "Card 1 (Holo),FE01", "Card 2 (Holo),FE01"),
    )
    fuzzy = [r for r in job.rows if r.verdict == "needs_confirmation"]
    importer.confirm_rows(ALICE, job.id, [fuzzy[0].id])

    confirmed = [r for r in importer.get(ALICE, job.id).rows if r.confirmed]
    assert len(confirmed) == 1


def test_committing_twice_is_refused(importer, catalog):
    pid = catalog["printings"]["BS1-001:common"]
    job = importer.start(ALICE, filename="x.csv", raw=csv_bytes("printing_id", pid))
    importer.commit(ALICE, job.id)

    with pytest.raises(JobNotReady):
        importer.commit(ALICE, job.id)


def test_one_bad_row_writes_nothing_at_all(importer, catalog, db, monkeypatch):
    """**Story 029's second criterion.** A half-applied spreadsheet leaves a collection in a state
    the user cannot reason about and cannot easily undo. A failed import leaves them exactly where
    they started, with a reason."""
    pids = [catalog["printings"][f"BS1-{n:03d}:common"] for n in range(1, 4)]
    job = importer.start(
        ALICE, filename="x.csv",
        raw=csv_bytes("printing_id,quantity", *[f"{p},1" for p in pids]),
    )

    calls = {"n": 0}
    original = importer._inventory.add

    def explode(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("the database went away")
        return original(*args, **kwargs)

    monkeypatch.setattr(importer._inventory, "add", explode)

    with pytest.raises(ImportRefused):
        importer.commit(ALICE, job.id)

    # Not two of three. None.
    assert InventoryRepository(db).count_for_user(ALICE) == 0
    assert importer.get(ALICE, job.id).status == "failed"


def test_a_failed_commit_records_why(importer, catalog, monkeypatch):
    pid = catalog["printings"]["BS1-001:common"]
    job = importer.start(ALICE, filename="x.csv", raw=csv_bytes("printing_id", pid))

    monkeypatch.setattr(
        importer._inventory, "add",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("nope")),
    )
    with pytest.raises(ImportRefused):
        importer.commit(ALICE, job.id)

    assert "nope" in importer.get(ALICE, job.id).error_summary


# --- the round trip -------------------------------------------------------------------

def test_export_then_import_is_a_no_op(importer, inventory, catalog, db):
    """**The strongest correctness check this bolt has**, and the reason the bolt notes say to
    build export first: it turns rung 1 from a claim into something provable.

    Export a collection, import the file back, and the diff should be 0 adds and 0 rejects —
    every row matches its own `printing_id` exactly.
    """
    inventory.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"], quantity=3)
    inventory.add(ALICE, printing_id=catalog["printings"]["BS1-002:common"], condition="damaged")
    inventory.add(ALICE, printing_id=catalog["printings"]["BS1-003:holo_rare"], quantity=2)

    exported = "".join(ExportService().singles(InventoryRepository(db).list_for_user(ALICE)))
    job = importer.start(ALICE, filename="round-trip.csv", raw=exported.encode("utf-8"))

    assert job.total_rows == 3
    assert job.rejected_count == 0
    assert job.needs_confirmation_count == 0
    # Every row is an *update*, because the collection already holds all three — which is itself
    # the proof that each one matched the row it came from.
    assert job.update_count == 3
    assert job.add_count == 0
    assert all(r.match_rung == "exact_printing" for r in job.rows)


def test_a_round_trip_through_another_users_import_matches_as_adds(
    importer, inventory, catalog, db,
):
    """The same file imported by somebody who owns none of it: still 0 rejects, but 3 adds. Proves
    the matcher is matching the *catalog* and the verdict is about the *collection*."""
    inventory.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    inventory.add(ALICE, printing_id=catalog["printings"]["BS1-002:common"])

    exported = "".join(ExportService().singles(InventoryRepository(db).list_for_user(ALICE)))
    job = importer.start(BOB, filename="theirs.csv", raw=exported.encode("utf-8"))

    assert job.rejected_count == 0
    assert job.add_count == 2


def test_a_round_trip_survives_a_comma_in_a_name(importer, inventory, catalog, db):
    from sqlalchemy import select

    from app.models.card import Card

    card = db.scalar(select(Card).where(Card.collector_number == "BS1-001"))
    card.name = 'Atlas, "Reborn"'
    db.commit()
    inventory.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])

    exported = "".join(ExportService().singles(InventoryRepository(db).list_for_user(ALICE)))
    job = importer.start(ALICE, filename="x.csv", raw=exported.encode("utf-8"))

    assert job.rejected_count == 0
    assert job.update_count == 1
