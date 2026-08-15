"""The gate refuses before it reaches the network.

FR-1's acceptance criteria under ADR-004, one test each. The cheapest tests in the suite and
among the most valuable: everything else asserts that we collect data correctly, and these assert
that we are in a fit state to collect it at all.

What changed with ADR-004 is worth stating, because a reader coming from the earlier version will
look for it: the gate no longer refuses a source whose terms prohibit us. That decision has been
made. It refuses a source where **nobody wrote down what the terms say and put their name to
accepting them** — and it refuses one that is currently being blocked.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.harvest.canonical import HarvestDescriptor
from app.harvest.gate import HarvestGate, SourceNotCleared
from app.models.price_source import PriceSource

HOST = "fake.test"
NOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)


def descriptor(**overrides) -> HarvestDescriptor:
    base = dict(
        name="fake", display_name="Fake", host=HOST,
        access_mode="scrape", reports_sold=False,
    )
    base.update(overrides)
    return HarvestDescriptor(**base)


def source_row(**overrides) -> PriceSource:
    base = dict(
        key="fake", name="Fake", base_url=f"https://{HOST}",
        access_mode="scrape", enabled=True,
        tos_review_note="Read 2026-08-15: the terms prohibit this. Accepted per ADR-004.",
        risk_accepted_by="Lars Kluijtmans",
        rate_limit_per_min=30, weight=1.0, reports_sold=False, quarantine_level=0,
    )
    base.update(overrides)
    return PriceSource(**base)


@pytest.fixture()
def gate() -> HarvestGate:
    return HarvestGate(allowed_hosts=frozenset({HOST}), contact_email="ops@example.com")


def test_a_source_with_an_accepted_risk_passes(gate):
    """Including one whose terms prohibit us. That is the whole of ADR-004: the note says so,
    a person accepted it, and the gate's job is to check that the record exists — not to
    re-litigate the decision."""
    gate.check(descriptor(), source_row(), now=NOW)


def test_a_source_with_no_row_cannot_run(gate):
    with pytest.raises(SourceNotCleared, match="no row in `price_sources`"):
        gate.check(descriptor(), None, now=NOW)


def test_a_disabled_source_cannot_run(gate):
    """The kill switch, which is the whole point of `enabled` being data rather than code."""
    with pytest.raises(SourceNotCleared, match="disabled"):
        gate.check(descriptor(), source_row(enabled=False), now=NOW)


@pytest.mark.parametrize("note", ["", "   ", None])
def test_an_enabled_source_without_a_review_note_cannot_run(gate, note):
    """Whitespace is not a review. The CHECK constraint says the same in SQL, but only this
    version can say it before a request goes out."""
    with pytest.raises(SourceNotCleared, match="no terms review note"):
        gate.check(descriptor(), source_row(tos_review_note=note), now=NOW)


@pytest.mark.parametrize("who", ["", "   ", None])
def test_a_source_with_nobody_accepting_the_risk_cannot_run(gate, who):
    """ADR-004 accepts a contractual risk per source. A risk accepted by nobody in particular is
    not an accepted risk."""
    with pytest.raises(SourceNotCleared, match="risk_accepted_by"):
        gate.check(descriptor(), source_row(risk_accepted_by=who), now=NOW)


def test_code_and_config_must_agree_on_access_mode(gate):
    """A `scrape` row must not run under a connector reviewed as an API, or the other way round.
    The review note describes one of the two, and guessing which is how the wrong review ends up
    in front of the wrong traffic."""
    with pytest.raises(SourceNotCleared, match="access_mode"):
        gate.check(descriptor(access_mode="official_api"), source_row(), now=NOW)


def test_a_host_off_the_allowlist_cannot_run(gate):
    with pytest.raises(SourceNotCleared, match="outbound allowlist"):
        gate.check(descriptor(host="elsewhere.example.net"), source_row(), now=NOW)


def test_without_a_contact_address_nothing_runs():
    """ADR-004 gave up politeness, not identifiability. An anonymous bot is one that can only be
    blocked, never asked to slow down — so this refusal comes before every other check."""
    gate = HarvestGate(allowed_hosts=frozenset({HOST}), contact_email="  ")

    with pytest.raises(SourceNotCleared, match="HARVEST_CONTACT_EMAIL"):
        gate.check(descriptor(), source_row(), now=NOW)


class TestQuarantine:
    """FR-18. A blocked source stops being asked; retrying into a block is how a temporary one
    becomes permanent."""

    def test_a_quarantined_source_cannot_run(self, gate):
        row = source_row(
            quarantined_until=NOW + timedelta(hours=2), quarantine_reason="5 refusals in one run"
        )
        with pytest.raises(SourceNotCleared, match="quarantined for another"):
            gate.check(descriptor(), row, now=NOW)

    def test_the_refusal_says_how_long_and_why(self, gate):
        row = source_row(
            quarantined_until=NOW + timedelta(hours=2), quarantine_reason="5 refusals in one run"
        )
        with pytest.raises(SourceNotCleared) as caught:
            gate.check(descriptor(), row, now=NOW)
        assert "5 refusals in one run" in str(caught.value)
        assert "120 minute" in str(caught.value)

    def test_an_expired_quarantine_lets_the_source_through(self, gate):
        row = source_row(quarantined_until=NOW - timedelta(minutes=1))
        gate.check(descriptor(), row, now=NOW)
