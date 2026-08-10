"""Set coverage — imported cards against the *declared* printed set size.

The unit brief's warning made operational: `sets.card_count` is what the publisher printed, so
comparing it against what we actually imported is the only thing standing between an
incomplete catalog and a completion percentage that silently reads 100%.

A wrong answer that looks right is worse than an obvious failure, so a shortfall is reported
loudly rather than rounded away.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..repositories.card_repository import CardRepository
from ..repositories.set_repository import SetRepository

_NUMBER = re.compile(r"^(?P<prefix>.*?)(?P<digits>\d+)$")


@dataclass(frozen=True, slots=True)
class CoverageReport:
    set_code: str
    expected: int
    imported: int
    missing_numbers: list[str]

    @property
    def is_complete(self) -> bool:
        # `expected == 0` means the set declared no printed size; nothing to assert against.
        return self.expected == 0 or self.imported >= self.expected

    @property
    def missing_count(self) -> int:
        return max(0, self.expected - self.imported)

    def as_dict(self) -> dict:
        return {
            "set_code": self.set_code,
            "expected": self.expected,
            "imported": self.imported,
            "missing_count": self.missing_count,
            "missing_numbers": self.missing_numbers,
        }


class CoverageService:
    def __init__(self, sets: SetRepository, cards: CardRepository) -> None:
        self._sets = sets
        self._cards = cards

    def coverage(self, set_code: str) -> CoverageReport | None:
        set_row = self._sets.get_by_code(set_code)
        if set_row is None:
            return None

        present = self._cards.collector_numbers_for_set(set_row.id)
        return CoverageReport(
            set_code=set_row.code,
            expected=set_row.card_count,
            imported=len(present),
            missing_numbers=_infer_missing(present, set_row.card_count),
        )


def _infer_missing(present: set[str], expected: int) -> list[str]:
    """Name the missing collector numbers when the numbering is unambiguous.

    TCG numbering is usually one prefix plus a zero-padded sequence (`BS1-001` … `BS1-126`),
    in which case the gaps can be named exactly. When it is not — mixed prefixes, no digits,
    nothing imported yet — we return an empty list rather than guess. An empty list means
    "undecidable", and `missing_count` still carries the shortfall.
    """
    if expected <= 0 or not present:
        return []

    prefixes: set[str] = set()
    widths: set[int] = set()
    seen: set[int] = set()

    for number in present:
        match = _NUMBER.match(number)
        if match is None:
            return []
        prefixes.add(match.group("prefix"))
        digits = match.group("digits")
        widths.add(len(digits))
        seen.add(int(digits))

    if len(prefixes) != 1 or len(widths) != 1:
        return []

    prefix = next(iter(prefixes))
    width = next(iter(widths))
    if max(seen) > expected:
        # The declared size disagrees with the numbering; naming gaps would mislead.
        return []

    return [f"{prefix}{n:0{width}d}" for n in range(1, expected + 1) if n not in seen]
