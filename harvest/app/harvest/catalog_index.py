"""An in-memory picture of the catalog, built once per run.

Both halves of a scan need the same thing: the planner turns the catalog into the questions to
ask, and the matcher turns the answers back into catalog rows. At the NFR's 50,000 tracked
printings this is a few megabytes, and holding it beats issuing a query per listing title
against a table that has not changed since the run started.

Pure data and lookups only — `repositories/catalog_snapshot_repository.py` builds it. Nothing
here touches a session, which is what lets the matcher be tested with a hand-written index
instead of a database.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field


def normalise(value: str) -> str:
    """Fold a title to comparable words: lowercase, alphanumerics, single-spaced.

    Punctuation goes because sellers write "Vipyro - FE01 012/126 *Holo*" and the catalog
    writes "Vipyro". Digits stay because the collector number is the strongest signal in most
    titles.
    """
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


@dataclass(frozen=True, slots=True)
class PrintingEntry:
    printing_id: str
    card_id: str
    card_name: str
    set_code: str
    set_name: str
    collector_number: str
    rarity: str
    finish: str
    language: str
    edition: str

    @property
    def normalised_name(self) -> str:
        return normalise(self.card_name)


@dataclass(frozen=True, slots=True)
class SealedEntry:
    sealed_product_id: str
    name: str
    kind: str
    set_code: str | None = None

    @property
    def normalised_name(self) -> str:
        return normalise(self.name)


@dataclass(frozen=True, slots=True)
class SetEntry:
    code: str
    name: str


@dataclass
class CatalogIndex:
    printings: list[PrintingEntry] = field(default_factory=list)
    sealed: list[SealedEntry] = field(default_factory=list)
    sets: list[SetEntry] = field(default_factory=list)

    #: Built in `__post_init__`; every lookup below reads these rather than re-scanning.
    _by_printing_id: dict[str, PrintingEntry] = field(default_factory=dict, init=False)
    _by_sealed_id: dict[str, SealedEntry] = field(default_factory=dict, init=False)
    _by_card_name: dict[str, list[PrintingEntry]] = field(default_factory=dict, init=False)
    _card_names_longest_first: list[str] = field(default_factory=list, init=False)
    _names_by_first_word: dict[str, list[str]] = field(default_factory=dict, init=False)
    _set_codes: dict[str, SetEntry] = field(default_factory=dict, init=False)
    _set_names: dict[str, SetEntry] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        for entry in self.printings:
            self._by_printing_id[entry.printing_id] = entry
            self._by_card_name.setdefault(entry.normalised_name, []).append(entry)
        for sealed in self.sealed:
            self._by_sealed_id[sealed.sealed_product_id] = sealed
        # Longest first so "Vipyro Ascended" is found before "Vipyro" in a title that contains
        # both — a shorter name matching first would silently pick the wrong card.
        self._card_names_longest_first = sorted(
            self._by_card_name, key=lambda name: (-len(name), name)
        )
        # Bucketed by first word so matching a title tests a handful of names instead of all
        # 5,000. At the NFR's tracked-printing count the naive scan is the matcher's whole
        # cost, and it is paid once per listing.
        for name in self._card_names_longest_first:
            first = name.split(" ", 1)[0]
            self._names_by_first_word.setdefault(first, []).append(name)
        for set_entry in self.sets:
            self._set_codes[normalise(set_entry.code)] = set_entry
            self._set_names[normalise(set_entry.name)] = set_entry

    # --- lookups -------------------------------------------------------------------

    @property
    def card_names_longest_first(self) -> list[str]:
        return self._card_names_longest_first

    def candidate_names_for(self, normalised_title: str) -> list[str]:
        """Card names worth testing against this title, longest first.

        Only names whose first word appears in the title. A name the title cannot contain is
        not a candidate, and this is what keeps the matcher linear in the title's length
        rather than in the size of the catalog.
        """
        words = set(normalised_title.split())
        names = [
            name
            for word in words
            for name in self._names_by_first_word.get(word, ())
        ]
        return sorted(set(names), key=lambda name: (-len(name), name))

    def printings_for_name(self, normalised_name: str) -> list[PrintingEntry]:
        return self._by_card_name.get(normalised_name, [])

    def set_by_code(self, code: str) -> SetEntry | None:
        return self._set_codes.get(normalise(code))

    def find_set_in(self, normalised_title: str) -> SetEntry | None:
        """Set code first, then set name. A code is unambiguous; a name can be a card name."""
        tokens = set(normalised_title.split())
        for code, entry in self._set_codes.items():
            if code in tokens:
                return entry
        for name, entry in self._set_names.items():
            if name and name in normalised_title:
                return entry
        return None

    def printing(self, printing_id: str) -> PrintingEntry | None:
        return self._by_printing_id.get(printing_id)

    def sealed_product(self, sealed_id: str) -> SealedEntry | None:
        return self._by_sealed_id.get(sealed_id)

    def search_text_for(self, product_id: str) -> tuple[str, str] | None:
        """`(query text, kind hint)` for a product the light scan wants neighbours of.

        Resolved here rather than by a cross-schema join in the listing query: the harvest tables
        hold ids, this index already holds the names, and keeping the join out of the hot query
        is what stops the service boundary becoming load-bearing for performance.
        """
        printing = self._by_printing_id.get(product_id)
        if printing is not None:
            return f"{printing.card_name} {printing.set_code}".strip(), "single"
        sealed = self._by_sealed_id.get(product_id)
        if sealed is not None:
            return sealed.name, "sealed"
        return None

    def is_empty(self) -> bool:
        return not self.printings and not self.sealed


def index_from(
    printings: Iterable[PrintingEntry],
    sealed: Iterable[SealedEntry],
    sets: Iterable[SetEntry],
) -> CatalogIndex:
    return CatalogIndex(
        printings=list(printings), sealed=list(sealed), sets=list(sets)
    )
