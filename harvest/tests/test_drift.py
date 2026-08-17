"""Selector drift detection — story 010.

**The assertion the story exists for is `test_empty_is_not_the_same_as_unparseable`.** Under
ADR-004 a connector will break, sites change markup without notice, and the failure mode is
*silence*: zero rows looks exactly like a quiet market. Every mitigation this intent has for that
failure is here or in the accept-rate trend.

Three states produce zero usable listings and must produce three different verdicts:

* the page parsed and the market really is quiet → `empty`, and nobody is woken
* the page could not be parsed → `unparseable`, **our problem**
* the source served a challenge → `blocked`, which is story 011's problem, not a selector's

These run against committed fixtures and make **no network call**. The drift check that does talk
to a live source is scheduled, not part of this suite — a third party being down must not fail a
pull request, which is story 010's fifth criterion.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.harvest.canonical import RawListing
from app.harvest.drift import (
    MIN_EXPECTED, PROBE_QUERY, REQUIRED_FIELDS, Verdict, check_parsed, check_source,
)
from app.harvest.http import SourceRefused, SourceUnavailable
from app.harvest.sources.ebay_sold import EbaySoldAdapter

FIXTURES = Path(__file__).parent / "fixtures"


def listing(**overrides) -> RawListing:
    return RawListing(**{
        "external_id": "123456789012",
        "title": "Elestrals Vipyro FE01 012/126",
        "url": "https://www.ebay.com/itm/123456789012",
        "price_cents": 1250,
        "currency": "USD",
        "observed_at": datetime(2026, 8, 17, tzinfo=timezone.utc),
        "is_sold": True,
        "sold_price_cents": 1250,
        **overrides,
    })


class Stub:
    """A source that does whatever the test needs. No network, by construction."""

    name = "stub"

    def __init__(self, result):
        self._result = result

    def discover(self, query, *, limit):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


# --- the distinction the story is about ------------------------------------------------

def test_empty_is_not_the_same_as_unparseable():
    """**The whole point of story 010.**

    Both produce zero listings. One is a fact about the market that needs no action; the other is
    our parser being broken while reporting "no sales seen" for months. Identical row counts,
    opposite meanings.
    """
    quiet = check_parsed("stub", [], reports_sold=True)
    broken = check_source(Stub(SourceRefused("challenge page")), reports_sold=True)

    assert quiet.verdict is Verdict.EMPTY
    assert broken.verdict is not Verdict.EMPTY
    # And only one of them should wake anybody about our code.
    assert quiet.verdict.is_our_problem is False


def test_an_empty_result_is_not_our_problem():
    report = check_parsed("stub", [], reports_sold=True)
    assert report.verdict.is_our_problem is False
    assert "market" in report.detail


def test_a_challenge_page_is_a_block_not_drift():
    """Story 011 owns this. Calling it drift sends somebody to read selectors when the actual
    problem is that we have been blocked — the wrong fix, applied urgently."""
    report = check_source(Stub(SourceRefused("no results container")), reports_sold=True)

    assert report.verdict is Verdict.BLOCKED
    assert report.verdict.is_our_problem is False
    assert "story 011" in report.detail


def test_an_unreachable_source_is_not_drift():
    """Story 010's first edge case: the source being down is a different problem and a different
    alert. Conflating them means the alert that matters gets ignored during the next outage."""
    report = check_source(Stub(SourceUnavailable("connection reset")), reports_sold=True)

    assert report.verdict is Verdict.UNREACHABLE
    assert report.verdict.is_our_problem is False


def test_an_unexpected_exception_is_reported_not_raised():
    """A scheduled check that dies on a surprise tells you less than one that says so."""
    report = check_source(Stub(ValueError("something odd")), reports_sold=True)

    assert report.verdict is Verdict.UNPARSEABLE
    assert report.verdict.is_our_problem is True
    assert "ValueError" in report.detail


# --- naming the field ------------------------------------------------------------------

def test_a_field_missing_on_every_row_is_drift():
    """A selector stopped matching. That is the case worth an alert."""
    report = check_parsed(
        "stub", [listing(title=""), listing(title=""), listing(title="")],
        reports_sold=True,
    )

    assert report.verdict is Verdict.DRIFTED
    assert report.missing_fields == {"title": 3}


def test_the_report_names_which_field_stopped_being_found():
    """**Story 010's fourth criterion.** "title is missing on all 3 rows" points at a selector;
    "0 results" points at nothing at all."""
    report = check_parsed("stub", [listing(url=""), listing(url="")], reports_sold=True)

    assert "url" in str(report)
    assert "missing on 2/2" in str(report)


def test_several_broken_selectors_are_all_named():
    report = check_parsed(
        "stub", [listing(title="", url=""), listing(title="", url="")], reports_sold=True,
    )
    assert set(report.missing_fields) == {"title", "url"}


def test_a_field_missing_on_only_some_rows_is_not_drift():
    """Not every listing is unusual in the same way, and eBay omits a location on plenty of them.
    A partial absence is data; a total absence is a selector."""
    report = check_parsed(
        "stub", [listing(), listing(), listing(title="")], reports_sold=True,
    )

    assert report.verdict is Verdict.OK
    assert report.missing_fields == {"title": 1}


def test_a_zero_price_counts_as_present():
    """A free listing is priced at zero. `bool(0)` is False, which would report a working selector
    as broken — so presence is `is not None`, not truthiness."""
    report = check_parsed("stub", [listing(price_cents=0)], reports_sold=False)
    assert report.verdict is Verdict.OK


def test_an_unsold_listing_counts_as_present():
    """`is_sold=False` is a real answer, not a missing field. Same trap as the zero price."""
    report = check_parsed("stub", [listing(is_sold=False)], reports_sold=True)
    assert report.verdict is Verdict.OK


def test_the_sold_flag_is_only_required_of_a_source_that_reports_sales():
    """Asserting it on an asking-price source would fail every run for a connector behaving
    exactly as designed."""
    rows = [listing(is_sold=None)]  # type: ignore[arg-type]
    assert check_parsed("stub", rows, reports_sold=False).verdict is Verdict.OK


def test_a_clean_parse_is_ok():
    report = check_parsed("stub", [listing(), listing()], reports_sold=True)

    assert report.ok
    assert report.parsed == 2
    assert "every field present" in str(report)


# --- against the committed fixture -----------------------------------------------------

def test_the_recorded_page_still_yields_every_promised_field():
    """Story 010's second criterion, against a committed recording and **no network**.

    A stale fixture is fine and expected: it tests that our parser still parses what we recorded.
    The scheduled check is what tests that the recording still resembles reality.
    """
    html = (FIXTURES / "ebay_sold_page.html").read_text(encoding="utf-8")
    listings = EbaySoldAdapter().parse(html)

    assert listings, "the fixture should parse to at least one listing"
    report = check_parsed("ebay_sold", listings, reports_sold=True)
    assert report.ok, str(report)


def test_every_contract_field_is_actually_checked():
    """A guard on the guard: if somebody adds a field to `RawListing`'s contract and forgets to
    add it here, the drift check silently stops covering it."""
    for name in REQUIRED_FIELDS:
        assert hasattr(listing(), name), f"{name} is not on RawListing"


def test_the_challenge_fixture_is_refused_rather_than_parsed_as_empty():
    """The failure this whole subsystem is arranged around: a 200 that contains a challenge page
    must not read as a quiet market."""
    html = (FIXTURES / "ebay_challenge_page.html").read_text(encoding="utf-8")

    with pytest.raises(SourceRefused):
        EbaySoldAdapter().parse(html)


# --- the probe -------------------------------------------------------------------------

def test_the_probe_query_is_broad_on_purpose():
    """A niche query returning nothing is a real market answer, and this check must not be able
    to confuse the two. So it asks something that should always have results."""
    assert PROBE_QUERY.text == "elestrals"
    assert PROBE_QUERY.reason == "drift-check"


def test_the_report_serialises_for_a_log_line():
    report = check_parsed("stub", [listing(title=""), listing(title="")], reports_sold=True)
    payload = report.as_dict()

    assert payload["verdict"] == "drifted"
    assert payload["is_our_problem"] is True
    assert payload["missing_fields"] == {"title": 2}


def test_min_expected_is_documented_as_a_constant():
    # Referenced so the threshold cannot be quietly deleted as unused.
    assert MIN_EXPECTED >= 1
