"""The matching ladder — story 028's core, and the part that will take longer than it looks.

Five rungs, most to least confident. Each records which rung it landed on, and the UI treats them
differently:

| Rung | Match on | Applied without confirmation? |
|---|---|---|
| 1 `exact_printing` | `printing_id` | yes — our own export round-tripping |
| 2 `natural_key` | set + number + finish + language + edition | yes |
| 3 `set_and_number` | set + number, defaults applied | yes, flagged in the diff |
| 4 `fuzzy_name` | normalised name + set | **no — per-row confirmation** |
| 5 `none` | nothing | rejected, with a reason |

**Below the similarity floor is a rejection, not a low-confidence match.** That line is the whole
design, and the bolt notes say to hold it under schedule pressure: a confident wrong match silently
corrupts a collection somebody has kept for years, and they will not find out until they go looking
for a card they no longer appear to own. An honest failure costs them one row of manual work.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.card import Card
from ..models.printing import Printing
from ..models.set import Set
from .import_parser import normalise_name, split_name_hints

#: Below this, a name is not a match. Tuned to accept a typo or a missing apostrophe and reject a
#: different card — `"Vipyro"` vs `"Vipyra"` is 0.83 and both are real cards, which is exactly why
#: the floor is high and rung 4 still needs a human.
SIMILARITY_FLOOR = 0.86

#: Applied at rung 3, where the file gave a set and number but nothing about the printing.
DEFAULT_LANGUAGE = "en"


@dataclass(frozen=True, slots=True)
class MatchResult:
    printing_id: str | None
    rung: str
    score: float | None
    reason: str | None = None

    @property
    def matched(self) -> bool:
        return self.printing_id is not None

    @property
    def needs_confirmation(self) -> bool:
        """Only rung 4. Rungs 1–3 are identity or near-identity; rung 4 is a guess with a number
        attached, and a guess about somebody's collection is theirs to accept."""
        return self.rung == "fuzzy_name"


class ImportMatcher:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._name_index: dict[str, list[tuple[str, str]]] | None = None

    def match(self, values: dict[str, str]) -> MatchResult:
        """Walk the ladder, stopping at the first rung that answers."""
        for rung in (self._by_printing_id, self._by_natural_key, self._by_set_and_number,
                     self._by_fuzzy_name):
            result = rung(values)
            if result is not None:
                return result

        return MatchResult(
            printing_id=None, rung="none", score=None,
            # Names what was actually tried, so the uploader can see which column to fix rather
            # than being told "no match" about a row with five populated columns.
            reason=self._why_not(values),
        )

    # --- rung 1 ---------------------------------------------------------------------

    def _by_printing_id(self, values: dict[str, str]) -> MatchResult | None:
        printing_id = (values.get("printing_id") or "").strip()
        if not printing_id:
            return None
        if self._db.get(Printing, printing_id) is None:
            # A printing id that is not ours: almost certainly a stale export against a rebuilt
            # catalog. Fall through rather than reject — the other columns may still identify it.
            return None
        return MatchResult(printing_id=printing_id, rung="exact_printing", score=1.0)

    # --- rung 2 ---------------------------------------------------------------------

    def _by_natural_key(self, values: dict[str, str]) -> MatchResult | None:
        set_code = (values.get("set_code") or "").strip()
        number = (values.get("collector_number") or "").strip()
        finish = (values.get("finish") or "").strip().lower()
        if not (set_code and number and finish):
            return None

        stmt = self._printing_stmt(set_code, number).where(
            func.lower(Printing.finish) == finish
        )
        language = (values.get("language") or "").strip().lower()
        if language:
            stmt = stmt.where(func.lower(Printing.language) == language)
        edition = (values.get("edition") or "").strip().lower()
        if edition:
            stmt = stmt.where(func.lower(Printing.edition) == edition)

        found = list(self._db.scalars(stmt))
        if len(found) == 1:
            return MatchResult(printing_id=found[0].id, rung="natural_key", score=1.0)
        return None

    # --- rung 3 ---------------------------------------------------------------------

    def _by_set_and_number(self, values: dict[str, str]) -> MatchResult | None:
        """Set and number alone, with defaults applied.

        Ambiguity here is a *rejection*, not a coin flip: a card with a normal and a foil printing
        and nothing in the file to tell them apart is a question, and picking one silently records
        a card the collector may not own in a condition they never stated.
        """
        set_code = (values.get("set_code") or "").strip()
        number = (values.get("collector_number") or "").strip()
        if not (set_code and number):
            return None

        found = list(self._db.scalars(self._printing_stmt(set_code, number)))
        if not found:
            return None
        if len(found) == 1:
            return MatchResult(printing_id=found[0].id, rung="set_and_number", score=0.95)

        # More than one printing. Try the language default before giving up — most files that omit
        # finish are English, and that narrows many cards to one.
        english = [p for p in found if (p.language or "").lower() == DEFAULT_LANGUAGE]
        if len(english) == 1:
            return MatchResult(printing_id=english[0].id, rung="set_and_number", score=0.9)

        return MatchResult(
            printing_id=None, rung="none", score=None,
            reason=(
                f"{set_code} {number} has {len(found)} printings and the file does not say which "
                "— add a finish column"
            ),
        )

    # --- rung 4 ---------------------------------------------------------------------

    def _by_fuzzy_name(self, values: dict[str, str]) -> MatchResult | None:
        raw_name = (values.get("name") or "").strip()
        if not raw_name:
            return None

        hints = split_name_hints(raw_name)
        target = normalise_name(hints.name)
        if not target:
            return None

        set_code = (values.get("set_code") or "").strip().upper()

        best_score = 0.0
        best_card: str | None = None
        for normalised, entries in self._names().items():
            score = SequenceMatcher(None, target, normalised).ratio()
            if score <= best_score:
                continue
            for card_id, card_set in entries:
                if set_code and card_set.upper() != set_code:
                    continue
                best_score, best_card = score, card_id

        if best_card is None or best_score < SIMILARITY_FLOOR:
            return None

        printings = list(self._db.scalars(
            select(Printing).where(Printing.card_id == best_card)
        ))
        if hints.finish:
            narrowed = [p for p in printings if (p.finish or "").lower() == hints.finish]
            if narrowed:
                printings = narrowed
        if len(printings) != 1:
            return MatchResult(
                printing_id=None, rung="none", score=best_score,
                reason=(
                    f"“{raw_name}” looks like a card we have, but it has {len(printings)} "
                    "printings and the file does not say which"
                ),
            )

        return MatchResult(
            printing_id=printings[0].id, rung="fuzzy_name", score=round(best_score, 3),
        )

    # --- helpers --------------------------------------------------------------------

    def _printing_stmt(self, set_code: str, number: str):
        return (
            select(Printing)
            .join(Card, Card.id == Printing.card_id)
            .join(Set, Set.id == Card.set_id)
            .where(
                func.lower(Set.code) == set_code.lower(),
                func.lower(Card.collector_number) == number.lower(),
            )
        )

    def _names(self) -> dict[str, list[tuple[str, str]]]:
        """The fuzzy index, built once per job rather than per row.

        A 5,000-row file against a 5,000-card catalog is 25 million comparisons if the catalog is
        re-read each time. Built once, it is 25 million cheap string ratios instead — which is what
        keeps the 30-second dry-run budget reachable.
        """
        if self._name_index is None:
            index: dict[str, list[tuple[str, str]]] = {}
            rows = self._db.execute(
                select(Card.id, Card.name, Set.code).join(Set, Set.id == Card.set_id)
            ).all()
            for card_id, name, set_code in rows:
                index.setdefault(normalise_name(name), []).append((card_id, set_code or ""))
            self._name_index = index
        return self._name_index

    @staticmethod
    def _why_not(values: dict[str, str]) -> str:
        populated = {k for k, v in values.items() if (v or "").strip()}
        if not populated:
            return "the row is empty once mapped — check the column mapping"
        if "name" not in populated and "collector_number" not in populated:
            return "no card name and no collector number — check the column mapping"
        if "set_code" in populated and "collector_number" in populated:
            return (
                f"no card {values.get('collector_number')!r} in set "
                f"{values.get('set_code')!r}"
            )
        if "name" in populated:
            return f"no card close enough to {values.get('name')!r}"
        return "could not identify a card from this row"
