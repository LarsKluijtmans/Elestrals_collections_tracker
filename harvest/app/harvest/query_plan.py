"""What each scan asks. The only difference between the two modes lives in this file.

    deep    every question the catalog can generate — generic sweeps, then sealed products,
            then sets, then card names. Finds what we have never seen. Expensive by design.
    light   no catalog sweep at all. The runner re-checks known listings by id, and this file
            supplies only a short list of "more like this" queries aimed at products whose
            market just moved.

Both plans are **capped and ordered**, and the order is the important half. A cap that
truncates a randomly-ordered plan silently drops whichever queries happened to sort last; a
cap that truncates this plan drops the least valuable queries first, because the broadest
sweeps are generated before the narrowest ones. `HarvestRun.queries` records how many actually
ran, so a plan that is being truncated says so in the operations console rather than in
nobody's imagination.

Every query carries a `reason`, which is what makes a 400-query run readable afterwards.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .canonical import Query
from .catalog_index import CatalogIndex

#: The brand term every query is anchored on. Without it a search for a card name returns the
#: whole trading-card market, and the matcher spends the run rejecting Pokémon.
BRAND = "elestrals"

#: Sealed formats as a seller writes them, not as `SEALED_KINDS` spells them.
SEALED_SWEEPS = (
    "booster box", "booster pack", "starter deck", "elite box", "sealed case", "bundle",
)


@dataclass(frozen=True, slots=True)
class Focus:
    """A product the light scan should look for near neighbours of."""

    text: str
    reason: str
    kind_hint: str | None = None


def deep_plan(index: CatalogIndex, *, max_queries: int) -> list[Query]:
    """The whole query space, broadest first.

    Broadest first is not tidiness. A deep run that hits its cap has still asked the questions
    that discover products missing from the catalog entirely — which is the one thing a light
    run can never do, and therefore the one thing a deep run must not skip.
    """
    queries: list[Query] = [Query(text=BRAND, reason="brand sweep")]

    for sweep in SEALED_SWEEPS:
        queries.append(Query(
            text=f"{BRAND} {sweep}", reason="sealed format sweep", kind_hint="sealed",
        ))

    for entry in index.sealed:
        queries.append(Query(
            text=f"{BRAND} {entry.name}", reason="catalog sealed product", kind_hint="sealed",
        ))

    for set_entry in index.sets:
        queries.append(Query(text=f"{BRAND} {set_entry.name}", reason="catalog set"))
        if set_entry.code and set_entry.code.lower() != set_entry.name.lower():
            queries.append(Query(text=f"{BRAND} {set_entry.code}", reason="catalog set code"))

    # Card names last: the most numerous and the most redundant, since a set sweep already
    # returns most of them. They earn their place by catching the cards nobody lists with a
    # set name — which, on a marketplace, is most of them.
    for name in _card_names(index):
        queries.append(Query(text=f"{BRAND} {name}", reason="catalog card", kind_hint="single"))

    return _dedupe(queries)[:max_queries]


def light_plan(focuses: Sequence[Focus], *, max_queries: int) -> list[Query]:
    """"Are there new ones like the ones we know?" — and nothing else.

    Deliberately not a shrunken deep plan. A light scan that re-swept the catalog would cost
    nearly what a deep scan costs and would mostly re-discover what it already holds; its job
    is the two questions the deep scan is too expensive to ask often: *are our known listings
    still live*, and *did something new appear next to them*.
    """
    queries = [
        Query(text=f"{BRAND} {focus.text}", reason=focus.reason, kind_hint=focus.kind_hint)
        for focus in focuses
        if focus.text.strip()
    ]
    return _dedupe(queries)[:max_queries]


def _card_names(index: CatalogIndex) -> Iterable[str]:
    """Distinct card names, in catalog order, so the plan is stable between runs.

    Stability matters when a cap truncates: a plan that reshuffles every night asks a
    different arbitrary 400 each time, and no product is ever covered twice in a row.
    """
    seen: set[str] = set()
    for entry in index.printings:
        key = entry.card_name.strip()
        if key and key.lower() not in seen:
            seen.add(key.lower())
            yield key


def _dedupe(queries: list[Query]) -> list[Query]:
    """First occurrence wins, so the earlier (broader) reason is the one recorded."""
    seen: set[str] = set()
    out: list[Query] = []
    for query in queries:
        key = " ".join(query.text.lower().split())
        if key in seen:
            continue
        seen.add(key)
        out.append(query)
    return out
