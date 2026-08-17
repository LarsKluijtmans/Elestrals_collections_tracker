"""Reading somebody else's spreadsheet — story 028's first half.

Real collector spreadsheets are messy in *specific, recurring* ways, and this file is a list of
those ways rather than a general-purpose CSV library:

* saved from Excel on Windows, so **CP1252** with a **semicolon** delimiter and a **BOM**
* quantity under a header called `#`, or `Qty`, or `Count`
* `"Vipyro (Holo)"` crammed into one name column
* set *names* where we expect set *codes*
* blank rows in the middle, because somebody grouped things visually

Everything here treats the upload as untrusted: bounded size, bounded rows, no formula evaluation,
and nothing from the file reaches SQL or a log line unescaped.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

#: Bounds. A file larger than this is refused with a message rather than partially processed —
#: story 028's last criterion, and the difference between "too big, split it" and a timeout.
MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = 20_000

#: Tried in order. UTF-8 first because it is correct; CP1252 last because it never fails — every
#: byte sequence is *valid* CP1252, so trying it earlier would silently mojibake real UTF-8.
ENCODINGS = ("utf-8-sig", "utf-8", "cp1252")

DELIMITERS = (",", ";", "\t", "|")

#: Header spellings seen in the wild, per field we care about. Lower-cased and stripped of
#: punctuation before lookup, so `Qty.` and `qty` both land here.
HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "printing_id": ("printingid", "printing", "printing id"),
    "set_code": ("setcode", "set", "setname", "set name", "edition set", "expansion"),
    "collector_number": (
        "collectornumber", "collector number", "number", "no", "num", "cardnumber",
        "card number", "cardno", "id",
    ),
    "name": ("name", "cardname", "card name", "card", "title"),
    "rarity": ("rarity", "rar"),
    "finish": ("finish", "foil", "foiling", "variant", "printing type"),
    "language": ("language", "lang"),
    "edition": ("edition", "ed"),
    "condition": ("condition", "cond", "grade condition", "state"),
    "quantity": ("quantity", "qty", "count", "#", "amount", "have", "owned"),
    "is_graded": ("isgraded", "graded"),
    "grader": ("grader", "gradingcompany", "grading company"),
    "grade": ("grade", "gradevalue"),
    "acquired_on": ("acquiredon", "acquired on", "purchasedate", "purchase date", "bought"),
    "acquired_unit_price_cents": ("acquiredunitpricecents", "pricepaid", "price paid", "cost"),
    "acquired_currency": ("acquiredcurrency", "currency"),
    "storage_location": ("storagelocation", "storage location", "location", "binder", "box"),
    "notes": ("notes", "note", "comment", "comments"),
    "is_for_trade": ("isfortrade", "for trade", "fortrade", "trade", "tradeable"),
}

#: `"Vipyro (Holo)"` — the qualifier is a finish hint, not part of the name.
FINISH_HINTS = {
    "holo": "foil", "foil": "foil", "holofoil": "foil",
    "reverse": "reverse_foil", "reverse holo": "reverse_foil", "reverse foil": "reverse_foil",
    "prismatic": "prismatic", "normal": "normal", "non-foil": "normal", "nonfoil": "normal",
}


class ImportTooLarge(ValueError):
    """Refused up front, with a message. Partially processing a too-big file is the failure mode
    story 028's last criterion exists to prevent."""


@dataclass(frozen=True, slots=True)
class ParsedFile:
    encoding: str
    delimiter: str
    headers: list[str]
    #: `(line_number, {header: cell})`. Line numbers are 1-based *as the spreadsheet shows them*,
    #: so a rejection saying "row 900" names a row the user can find.
    rows: list[tuple[int, dict[str, str]]]
    #: Blank rows found and skipped. Reported rather than hidden — somebody who exported 500 rows
    #: and sees 480 parsed deserves to know the other 20 were empty, not lost.
    blank_rows: int = 0


@dataclass
class NameHints:
    name: str
    finish: str | None = None
    extras: list[str] = field(default_factory=list)


def decode(raw: bytes) -> tuple[str, str]:
    """Decode the upload, returning `(text, encoding)`.

    Order matters and is not alphabetical. `utf-8-sig` first so a BOM is consumed rather than
    becoming an invisible character on the first header — which would make `printing_id` fail to
    match its own alias and silently break round-tripping of our *own* export. CP1252 last because
    it cannot fail: every byte is valid, so trying it early would turn real UTF-8 into mojibake
    without complaint.
    """
    if len(raw) > MAX_BYTES:
        raise ImportTooLarge(
            f"that file is {len(raw) // 1024 // 1024}MB; the limit is {MAX_BYTES // 1024 // 1024}MB"
        )

    for encoding in ENCODINGS:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    # Unreachable in practice — cp1252 accepts everything — but a silent mis-decode is worse than
    # an explicit refusal, so the impossible branch says so.
    raise ImportTooLarge("could not decode that file as UTF-8 or CP1252")


def sniff_delimiter(text: str) -> str:
    """Pick the delimiter from the header line.

    Counted on the first non-blank line rather than by `csv.Sniffer`, which guesses from a sample
    and is confidently wrong on files where a card name contains a semicolon. The header is the one
    line we can rely on being structural.
    """
    first = next((line for line in text.splitlines() if line.strip()), "")
    counts = {d: first.count(d) for d in DELIMITERS}
    best = max(counts, key=lambda d: counts[d])
    return best if counts[best] > 0 else ","


def parse(raw: bytes) -> ParsedFile:
    text, encoding = decode(raw)
    delimiter = sniff_delimiter(text)

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        headers = next(reader)
    except StopIteration:
        return ParsedFile(encoding=encoding, delimiter=delimiter, headers=[], rows=[])

    headers = [h.strip() for h in headers]
    rows: list[tuple[int, dict[str, str]]] = []
    blank = 0

    for index, cells in enumerate(reader, start=2):  # 1 is the header, as the user sees it
        if not any((cell or "").strip() for cell in cells):
            # Blank rows in the middle are how people group things visually. Skipped, counted,
            # and never rejected — an empty row is not an error the uploader needs to fix.
            blank += 1
            continue
        if len(rows) >= MAX_ROWS:
            raise ImportTooLarge(f"that file has more than {MAX_ROWS:,} rows; split it up")
        rows.append((index, {
            header: (cells[position].strip() if position < len(cells) else "")
            for position, header in enumerate(headers)
        }))

    return ParsedFile(
        encoding=encoding, delimiter=delimiter, headers=headers, rows=rows, blank_rows=blank,
    )


def normalise_header(header: str) -> str:
    return re.sub(r"[^a-z0-9# ]", "", header.strip().lower())


def suggest_mapping(headers: list[str]) -> dict[str, str]:
    """`{our_field: their_header}`, pre-filled and **editable**.

    A suggestion, never a decision. The dry run exists precisely because this can be wrong — story
    028's sixth criterion is quantity mis-mapped onto the collector-number column, and the point is
    that the resulting nonsense is *visible before commit* rather than prevented here.
    """
    seen = {normalise_header(h): h for h in headers if h.strip()}
    mapping: dict[str, str] = {}
    taken: set[str] = set()

    for field_name, aliases in HEADER_ALIASES.items():
        for alias in (field_name.replace("_", ""), *aliases):
            candidate = seen.get(normalise_header(alias))
            if candidate and candidate not in taken:
                mapping[field_name] = candidate
                taken.add(candidate)
                break

    return mapping


def split_name_hints(value: str) -> NameHints:
    """Pull `(Holo)`-style qualifiers out of a name column.

    `"Vipyro (Holo)"` is one of the most common shapes a collector spreadsheet takes, and matching
    on the whole string finds nothing. The qualifier is extracted as a *hint* rather than as a
    fact — it narrows the search, it does not assert the finish.
    """
    qualifiers = re.findall(r"\(([^)]*)\)", value)
    name = re.sub(r"\s*\([^)]*\)", "", value).strip()

    finish = None
    extras: list[str] = []
    for qualifier in qualifiers:
        key = qualifier.strip().lower()
        if key in FINISH_HINTS:
            finish = FINISH_HINTS[key]
        else:
            extras.append(qualifier.strip())

    return NameHints(name=name or value.strip(), finish=finish, extras=extras)


def normalise_name(value: str) -> str:
    """Case-folded, punctuation stripped, whitespace collapsed — the fuzzy matcher's input.

    Apostrophes are the reason this exists: `"Vipyro's Ember"` and `"Vipyros Ember"` are the same
    card typed by two people, and a straight comparison says they are not.
    """
    # Apostrophes are *removed*, not spaced: `"Vipyro's Ember"` and `"Vipyros Ember"` are the same
    # card typed by two people, and turning the first into `"vipyro s ember"` makes them differ by
    # a whole token — which is exactly the gap that pushes a real match below the similarity floor.
    without_apostrophes = re.sub(r"['’`]", "", value.casefold())
    folded = re.sub(r"[^a-z0-9 ]", " ", without_apostrophes)
    return re.sub(r"\s+", " ", folded).strip()
