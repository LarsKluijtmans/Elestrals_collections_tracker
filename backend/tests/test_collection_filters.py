"""The filter vocabulary — story 020, and the contract story 033 will reuse.

`FilterSet` is the single definition of what "Fire holos in NM" means, shared by the query string,
a saved view's JSON and (in phase 2) a valuation slice. The round-trip tests are the ones that
matter: if URL → FilterSet → JSON → FilterSet is not lossless, a saved view and the link you shared
mean different things, and the disagreement surfaces later as a valuation that does not match the
item list on screen.
"""
from __future__ import annotations

import pytest

from app.services.collection_filters import FilterSet, InvalidFilter


def test_an_empty_query_is_an_empty_filter():
    filters = FilterSet.from_params({})
    assert filters.is_empty
    assert filters.to_json() == {}
    # And it needs no joins at all — the default view every user lands on first.
    assert filters.needs_catalog_join is False


def test_repeated_parameters_become_an_or_within_the_attribute():
    filters = FilterSet.from_params({"element": ["fire", "water"]})
    assert filters.element == ("fire", "water")


def test_a_single_string_is_accepted_as_one_value():
    # `?element=fire` and `?element=fire&element=water` both have to work; a client that sends one
    # value should not have to know to wrap it.
    assert FilterSet.from_params({"element": "fire"}).element == ("fire",)


def test_duplicate_values_collapse_and_keep_their_order():
    filters = FilterSet.from_params({"element": ["fire", "water", "fire"]})
    assert filters.element == ("fire", "water")


def test_blank_values_are_dropped():
    # `?element=&element=fire` comes from a cleared select, and must not filter on the empty string.
    assert FilterSet.from_params({"element": ["", "  ", "fire"]}).element == ("fire",)


def test_tristate_flags_have_three_states():
    """`None` is a real third state. "Not filtering on graded" is a different query from
    "ungraded only", and collapsing them hides every graded card by default."""
    assert FilterSet.from_params({}).is_graded is None
    assert FilterSet.from_params({"is_graded": "true"}).is_graded is True
    assert FilterSet.from_params({"is_graded": "false"}).is_graded is False


@pytest.mark.parametrize("value", ["1", "yes", "TRUE"])
def test_truthy_spellings_are_accepted(value):
    assert FilterSet.from_params({"is_for_trade": value}).is_for_trade is True


def test_a_nonsense_boolean_is_rejected():
    with pytest.raises(InvalidFilter):
        FilterSet.from_params({"is_graded": "maybe"})


def test_an_unknown_condition_is_rejected_rather_than_returning_nothing():
    """A typo must not read as a fact about the collection. Silently returning zero rows for
    `condition=mnt` tells the collector they own none of those, which is a claim."""
    with pytest.raises(InvalidFilter):
        FilterSet.from_params({"condition": ["mnt"]})


def test_too_many_values_for_one_attribute_is_refused():
    with pytest.raises(InvalidFilter):
        FilterSet.from_params({"set_code": [f"FE{n:03d}" for n in range(60)]})


def test_unknown_keys_are_ignored_rather_than_rejected():
    """A saved view written by a later deploy must still open on an older one, minus the filter
    it does not understand. Rejecting would make a rollback break every view created since —
    and `?utm_source=` on a shared link must not 400 either."""
    filters = FilterSet.from_params({"element": ["fire"], "sparkliness": ["high"]})
    assert filters.element == ("fire",)
    assert "sparkliness" not in filters.to_json()


def test_the_search_term_is_bounded():
    long_term = "a" * 500
    assert len(FilterSet.from_params({"q": long_term}).q) == 100


# --- the round trip ------------------------------------------------------------------

def test_json_omits_what_was_not_set():
    # A stored view is the filters that were chosen, not a record of the ones that were not.
    filters = FilterSet.from_params({"element": ["fire"]})
    assert filters.to_json() == {"element": ["fire"]}


def test_a_full_filter_set_round_trips_losslessly():
    """The property saved views depend on. Every attribute, out and back."""
    original = FilterSet.from_params({
        "set_code": ["FE01", "FE02"],
        "element": ["fire"],
        "rarity": ["holo_rare"],
        "condition": ["near_mint", "mint"],
        "finish": ["foil"],
        "language": ["en"],
        "is_graded": "false",
        "is_for_trade": "true",
        "q": "atlas",
    })

    assert FilterSet.from_params(original.to_json()) == original


def test_a_tristate_false_survives_the_round_trip():
    """The one that a naive `if value:` serialiser loses. `is_graded=False` means "ungraded only";
    dropping it because it is falsy turns that view into "everything"."""
    original = FilterSet.from_params({"is_graded": "false"})
    assert original.to_json() == {"is_graded": False}
    assert FilterSet.from_params(original.to_json()).is_graded is False


# --- what needs a join ---------------------------------------------------------------

@pytest.mark.parametrize("params", [
    {"set_code": ["FE01"]}, {"element": ["fire"]}, {"rarity": ["rare"]},
    {"finish": ["foil"]}, {"language": ["en"]}, {"q": "atlas"},
])
def test_catalog_filters_need_the_catalog(params):
    assert FilterSet.from_params(params).needs_catalog_join is True


@pytest.mark.parametrize("params", [
    {"condition": ["near_mint"]}, {"is_graded": "true"}, {"is_for_trade": "true"},
])
def test_inventory_only_filters_do_not(params):
    """These answer from `inventory_items` alone, off the keyset index. Joining three tables to
    apply a predicate that lives on the row itself is a scan where a seek would do."""
    assert FilterSet.from_params(params).needs_catalog_join is False
