"""Value objects at the importer's boundary.

These are the *canonical* shapes every source must produce. An adapter's job is to emit
`RawRecord`s; the normaliser's job is to turn those into `CanonicalCard`s or `Rejection`s.
Nothing downstream of the normaliser ever sees a source-specific shape, which is what keeps
"add a source" to one file.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class RawRecord:
    """One row as the source delivered it, plus where it came from.

    `source_ref` is precise enough to fix by hand — "FE01.csv:42".
    """

    source_ref: str
    data: dict[str, str]


@dataclass(frozen=True, slots=True)
class PrintingKey:
    """The natural key, and the whole basis of idempotency.

    Equality by value, hashable, stable across runs *and across sources*: two sources
    describing the same physical card must produce an equal key or the catalog doubles.
    """

    set_code: str
    collector_number: str
    rarity: str
    finish: str
    language: str
    edition: str


@dataclass(frozen=True, slots=True)
class CanonicalPrinting:
    rarity: str
    finish: str
    language: str
    edition: str
    image_url: str | None = None
    is_tracked_for_price: bool = True

    def key(self, set_code: str, collector_number: str) -> PrintingKey:
        return PrintingKey(
            set_code=set_code,
            collector_number=collector_number,
            rarity=self.rarity,
            finish=self.finish,
            language=self.language,
            edition=self.edition,
        )


@dataclass(frozen=True, slots=True)
class CanonicalCard:
    """A card and every printing of it, complete or non-existent.

    There is no partial state: the normaliser either emits this whole, or a `Rejection`.
    """

    set_code: str
    collector_number: str
    name: str
    card_type: str
    printings: tuple[CanonicalPrinting, ...]
    element: str | None = None
    rune_type: str | None = None
    subtype: str | None = None
    attack: int | None = None
    defence: int | None = None
    spirit_cost: dict[str, int] | None = None
    rules_text: str | None = None
    flavour_text: str | None = None
    artist: str | None = None


@dataclass(frozen=True, slots=True)
class Rejection:
    """A record that could not be mapped, kept whole with a reason."""

    source_ref: str
    reason_code: str
    message: str
    field: str | None = None
    raw_record: dict[str, Any] | None = None


@dataclass
class ImportCounts:
    """Accumulated in memory, written once at terminal status."""

    sets_seen: int = 0
    cards_added: int = 0
    cards_updated: int = 0
    cards_unchanged: int = 0
    printings_added: int = 0
    rejected: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "sets_seen": self.sets_seen,
            "cards_added": self.cards_added,
            "cards_updated": self.cards_updated,
            "cards_unchanged": self.cards_unchanged,
            "printings_added": self.printings_added,
            "rejected": self.rejected,
        }


@dataclass(frozen=True, slots=True)
class SetMeta:
    """Set-level facts. `card_count` is the *printed* size — declared by the source, never
    counted from the rows we managed to import."""

    code: str
    name: str
    card_count: int
    series: str | None = None
    released_on: str | None = None
    logo_asset_url: str | None = None


@dataclass(frozen=True, slots=True)
class SourceDescriptor:
    name: str
    display_name: str
    #: False for the CSV seed. The robots.txt / rate-limit / user-agent machinery the unit
    #: brief requires of scrapers hangs off this flag, and none of it ships while it is False.
    requires_network: bool
    terms_url: str | None = None


@dataclass
class NormalisationResult:
    cards: list[CanonicalCard] = field(default_factory=list)
    rejections: list[Rejection] = field(default_factory=list)


class SourceAdapter(Protocol):
    """The port. One implementation per source; registered, never imported ad hoc."""

    name: str

    def describe(self) -> SourceDescriptor: ...

    def available_sets(self) -> list[str]: ...

    def set_meta(self, set_code: str) -> SetMeta: ...

    def fetch(self, set_code: str) -> Iterable[RawRecord]: ...
