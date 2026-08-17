"""CSV export — story 027, and **the definition of the import format**.

The bolt notes say to build this first, and they are right about why: export defines the shape, and
export→import round-tripping is the strongest correctness check available for the matcher. Without
it, the import's matching ladder is speculation; with it, rung 1 is testable on day one.

Two things here are security decisions rather than formatting ones.

**Formula injection.** A value beginning `=`, `+`, `-` or `@` is executed by Excel, Google Sheets
and LibreOffice when the file is opened. The attack is on *the user*, not on us: a crafted card note
becomes a formula in their spreadsheet, and `=IMPORTXML(...)` can exfiltrate the rest of the sheet.
So those values are prefixed with `'`, which spreadsheets strip on display and treat as text.

**Streaming.** Rows are yielded, never accumulated. 10,000 rows built into a list and joined is a
few hundred megabytes of Python strings for a file the user will open once, and the NFR bounds this
at 100MB RSS.
"""
from __future__ import annotations

import csv
import io
from collections.abc import Iterator

from ..models.inventory_item import InventoryItem
from ..models.sealed_inventory_item import SealedInventoryItem
from ..models.wishlist_item import WishlistItem

#: The canonical column order. **This is the import contract** — the importer's suggested mapping
#: recognises these spellings, and a round trip depends on them not moving.
SINGLES_COLUMNS = (
    # First, and deliberately: it is what makes a re-import an exact match rather than a search.
    "printing_id",
    "set_code",
    "collector_number",
    "name",
    "rarity",
    "finish",
    "language",
    "edition",
    "condition",
    "quantity",
    "is_graded",
    "grader",
    "grade",
    "acquired_on",
    "acquired_unit_price_cents",
    "acquired_currency",
    "storage_location",
    "notes",
    "is_for_trade",
)

SEALED_COLUMNS = (
    "sealed_product_id", "name", "kind", "quantity", "is_sealed",
    "acquired_on", "acquired_unit_price_cents", "acquired_currency",
    "storage_location", "notes",
)

WISHLIST_COLUMNS = (
    "printing_id", "set_code", "collector_number", "name", "rarity", "finish",
    "desired_quantity", "priority", "max_price_cents", "max_price_currency", "notes",
)

#: The four characters a spreadsheet treats as the start of a formula.
FORMULA_PREFIXES = ("=", "+", "-", "@")


def neutralise(value: object) -> str:
    """Render one cell, defusing anything a spreadsheet would execute.

    The prefix is `'`, which Excel, Sheets and LibreOffice all strip on display — so the user sees
    what they wrote and the cell is inert. Tab and carriage return are included because both are
    treated as formula-leading whitespace by at least one of the three.

    Note this runs on **our own export**, not only on imported content. The dangerous string got
    into the database through a note field somebody typed, and it is dangerous on the way out.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if text[:1] in FORMULA_PREFIXES or text[:1] in ("\t", "\r"):
        return f"'{text}"
    return text


def _line(writer: csv.writer, buffer: io.StringIO, values: list[str]) -> str:
    """Format one CSV line and hand back the buffer's contents.

    `csv.writer` is doing the quoting rather than hand-rolled string joining, because RFC 4180
    escaping has more corner cases than it looks — and one of them, a comma in a card name, shifts
    every later column by one and imports as something else entirely.
    """
    writer.writerow(values)
    line = buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)
    return line


class ExportService:
    """Streams CSV. Every method is a generator; nothing accumulates."""

    def singles(self, items: Iterator[InventoryItem] | list[InventoryItem]) -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\r\n")
        yield _line(writer, buffer, list(SINGLES_COLUMNS))

        for item in items:
            printing = item.printing
            card = printing.card if printing else None
            set_row = card.set if card else None
            yield _line(writer, buffer, [neutralise(v) for v in (
                item.printing_id,
                set_row.code if set_row else "",
                card.collector_number if card else "",
                card.name if card else "",
                printing.rarity if printing else "",
                printing.finish if printing else "",
                printing.language if printing else "",
                printing.edition if printing else "",
                item.condition,
                item.quantity,
                item.is_graded,
                item.grader,
                float(item.grade) if item.grade is not None else None,
                item.acquired_on,
                item.acquired_unit_price_cents,
                item.acquired_currency,
                item.storage_location,
                item.notes,
                item.is_for_trade,
            )])

    def sealed(self, items: list[SealedInventoryItem]) -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\r\n")
        yield _line(writer, buffer, list(SEALED_COLUMNS))

        for item in items:
            product = item.product
            yield _line(writer, buffer, [neutralise(v) for v in (
                item.sealed_product_id,
                product.name if product else "",
                product.kind if product else "",
                item.quantity,
                item.is_sealed,
                item.acquired_on,
                item.acquired_unit_price_cents,
                item.acquired_currency,
                item.storage_location,
                item.notes,
            )])

    def wishlist(self, items: list[WishlistItem]) -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\r\n")
        yield _line(writer, buffer, list(WISHLIST_COLUMNS))

        for item in items:
            printing = item.printing
            card = printing.card if printing else None
            set_row = card.set if card else None
            yield _line(writer, buffer, [neutralise(v) for v in (
                item.printing_id,
                set_row.code if set_row else "",
                card.collector_number if card else "",
                card.name if card else "",
                printing.rarity if printing else "",
                printing.finish if printing else "",
                item.desired_quantity,
                item.priority,
                item.max_price_cents,
                item.max_price_currency,
                item.notes,
            )])
