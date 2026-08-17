"""The collection filter vocabulary — story 020, and the thing story 033 will reuse.

**One definition, three consumers.** The query string on `/collection`, the JSON blob in
`saved_views`, and (in phase 2) the slice a valuation is computed over all mean the same thing by
"Fire holos in NM". Story 033 says so explicitly and says why: two implementations over one data
model will disagree, and the disagreement surfaces as a valuation that does not match the item list
on screen — which reads to a collector as the valuation being broken.

So `FilterSet` is the single definition. It parses from query parameters, round-trips through JSON,
and is the only thing that knows how to become SQL.

**The combining rule is AND across attributes, OR within one.** `element=fire&element=water` means
"fire or water"; adding `condition=near_mint` means "(fire or water) and near mint". That is what a
collector means by ticking boxes, and it is the rule story 020 states.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from sqlalchemy import ColumnElement, and_, or_

from ..models.card import Card
from ..models.inventory_item import CONDITIONS, InventoryItem
from ..models.printing import Printing
from ..models.set import Set

#: Attributes that take a list of values and OR within themselves. The tuple order is the order
#: the filter rail renders in, so it is a UI decision recorded once rather than in a component.
MULTI_VALUE = ("set_code", "element", "rarity", "condition", "finish", "language")

#: Tri-state flags: True, False, or absent-meaning-either. `None` is a real third state here —
#: "not filtering on graded" is not the same query as "ungraded only".
TRISTATE = ("is_graded", "is_for_trade")

SORTS = {
    # `added_desc` is the default because the last thing you added is the thing you are most
    # likely looking for — the fast-add flow makes that true rather than merely plausible.
    "added_desc": (InventoryItem.created_at.desc(), InventoryItem.id.asc()),
    "added_asc": (InventoryItem.created_at.asc(), InventoryItem.id.asc()),
    "quantity_desc": (InventoryItem.quantity.desc(), InventoryItem.id.asc()),
    "quantity_asc": (InventoryItem.quantity.asc(), InventoryItem.id.asc()),
    "name_asc": (Card.name.asc(), InventoryItem.id.asc()),
    "name_desc": (Card.name.desc(), InventoryItem.id.asc()),
}
DEFAULT_SORT = "added_desc"

#: Sorts whose leading column lives on a joined table. They need the join even when no filter
#: does, and forgetting that is a `NoForeignKeysError` at request time rather than at import.
SORTS_NEEDING_CARD = ("name_asc", "name_desc")

MAX_VALUES_PER_ATTRIBUTE = 50


class InvalidFilter(ValueError):
    """A filter value outside the vocabulary. A 400, not a silent empty result.

    Returning zero rows for `condition=mnt` would read as "you own none of those" — a factual
    claim about the collection, made on the basis of a typo.
    """


@dataclass(frozen=True, slots=True)
class FilterSet:
    set_code: tuple[str, ...] = ()
    element: tuple[str, ...] = ()
    rarity: tuple[str, ...] = ()
    condition: tuple[str, ...] = ()
    finish: tuple[str, ...] = ()
    language: tuple[str, ...] = ()
    is_graded: bool | None = None
    is_for_trade: bool | None = None
    #: Free-text over the card name. Not in `MULTI_VALUE`: it is one term, ANDed like the rest.
    q: str | None = None

    # --- construction ---------------------------------------------------------------

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> FilterSet:
        """Build from query parameters or from a saved view's JSON — the same shape either way.

        Unknown keys are **ignored rather than rejected**. A saved view written by a later deploy
        that learned a new filter should still open on an older one, minus the filter it does not
        understand; refusing would make a rollback break every saved view created since.
        """
        values: dict[str, Any] = {}

        for name in MULTI_VALUE:
            raw = params.get(name)
            if raw is None:
                continue
            items = [raw] if isinstance(raw, str) else list(raw)
            cleaned = tuple(dict.fromkeys(v for v in (s.strip() for s in items) if v))
            if len(cleaned) > MAX_VALUES_PER_ATTRIBUTE:
                raise InvalidFilter(
                    f"{name}: at most {MAX_VALUES_PER_ATTRIBUTE} values"
                )
            if cleaned:
                values[name] = cleaned

        for name in TRISTATE:
            raw = params.get(name)
            if raw is None:
                continue
            values[name] = _as_bool(name, raw)

        q = params.get("q")
        if isinstance(q, str) and q.strip():
            values["q"] = q.strip()[:100]

        built = cls(**values)
        built.validate()
        return built

    def validate(self) -> None:
        for value in self.condition:
            if value not in CONDITIONS:
                raise InvalidFilter(f"unknown condition {value!r}")

    # --- serialisation --------------------------------------------------------------

    def to_json(self) -> dict[str, Any]:
        """What `saved_views.filters` stores. Empty attributes are omitted, so a stored view is
        the filters that were set rather than a full record of the ones that were not."""
        out: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if value in ((), None, ""):
                continue
            out[f.name] = list(value) if isinstance(value, tuple) else value
        return out

    @property
    def is_empty(self) -> bool:
        return self.to_json() == {}

    # --- SQL ------------------------------------------------------------------------

    @property
    def needs_catalog_join(self) -> bool:
        """Whether answering this needs `printings`/`cards`/`sets` at all.

        Worth asking: an unfiltered collection is the common case and the default view, and it
        answers from `inventory_items` alone off the keyset index. Joining three tables to apply
        no predicate is the difference between a seek and a scan on the exact page every user
        lands on first.
        """
        return bool(
            self.set_code or self.element or self.rarity or self.finish
            or self.language or self.q
        )

    def conditions(self) -> list[ColumnElement[bool]]:
        """The WHERE clauses. AND across attributes, OR within one — story 020's rule, here."""
        clauses: list[ColumnElement[bool]] = []

        if self.condition:
            clauses.append(InventoryItem.condition.in_(self.condition))
        if self.is_graded is not None:
            clauses.append(InventoryItem.is_graded.is_(self.is_graded))
        if self.is_for_trade is not None:
            clauses.append(InventoryItem.is_for_trade.is_(self.is_for_trade))

        if self.set_code:
            clauses.append(Set.code.in_(self.set_code))
        if self.element:
            clauses.append(Card.element.in_(self.element))
        if self.rarity:
            clauses.append(Printing.rarity.in_(self.rarity))
        if self.finish:
            clauses.append(Printing.finish.in_(self.finish))
        if self.language:
            clauses.append(Printing.language.in_(self.language))
        if self.q:
            # Prefix and infix, matching the catalog search's tolerance. A collector filtering
            # their own collection is usually completing a half-remembered name.
            clauses.append(Card.name.ilike(f"%{_escape_like(self.q)}%"))

        return clauses

    def where(self, user_sub: str) -> ColumnElement[bool]:
        """Ownership first, always, and not as one clause among equals — it is the only one that
        is a security property rather than a preference."""
        return and_(InventoryItem.user_sub == user_sub, *self.conditions()) \
            if self.conditions() else InventoryItem.user_sub == user_sub


def _as_bool(name: str, raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if text in ("true", "1", "yes"):
        return True
    if text in ("false", "0", "no"):
        return False
    raise InvalidFilter(f"{name}: expected a boolean, got {raw!r}")


def _escape_like(term: str) -> str:
    """`%` and `_` in a user's search term are literal characters, not wildcards.

    Without this, searching for `_` matches every card with at least one character in its name —
    which looks like the filter being ignored.
    """
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# Re-exported so callers do not import the SQLAlchemy models to name a sort.
__all__ = [
    "FilterSet", "InvalidFilter", "SORTS", "DEFAULT_SORT", "MULTI_VALUE", "TRISTATE",
    "SORTS_NEEDING_CARD",
]
