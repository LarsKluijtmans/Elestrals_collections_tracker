"""The backoff arithmetic — FR-18.

Pure policy, so it is tested without waiting and without a database. The escalation is the part
worth pinning down: a source that refuses us twice in a row is not more likely to relent on the
same schedule, and a source that recovers must not be punished for having been blocked last month.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.harvest.quarantine import QuarantinePolicy

NOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def policy() -> QuarantinePolicy:
    return QuarantinePolicy(
        threshold=5, base_minutes=60, backoff_factor=4.0, max_minutes=2880
    )


class TestTheThreshold:
    @pytest.mark.parametrize("refusals", [0, 1, 4])
    def test_a_few_refusals_are_not_a_block(self, policy, refusals):
        """One 403 among 400 queries is a listing we are not allowed to see; one 429 is ordinary
        traffic shaping, which the HTTP layer already backs off for. Quarantine is for a
        *sustained* pattern."""
        assert policy.should_quarantine(refusals) is False

    @pytest.mark.parametrize("refusals", [5, 6, 50])
    def test_a_sustained_pattern_is(self, policy, refusals):
        assert policy.should_quarantine(refusals) is True


class TestTheBackoff:
    def test_the_first_quarantine_is_the_base(self, policy):
        assert policy.duration_for(1) == timedelta(minutes=60)

    def test_each_consecutive_one_escalates(self, policy):
        assert policy.duration_for(2) == timedelta(minutes=240)
        assert policy.duration_for(3) == timedelta(minutes=960)

    def test_it_stops_at_the_ceiling(self, policy):
        """Escalating forever would turn a bad week into a permanently dark source with nobody
        deciding that."""
        assert policy.duration_for(9) == timedelta(minutes=2880)
        assert policy.duration_for(99) == timedelta(minutes=2880)

    def test_level_zero_is_treated_as_the_first(self, policy):
        assert policy.duration_for(0) == timedelta(minutes=60)

    def test_until_is_now_plus_the_duration(self, policy):
        assert policy.until(NOW, 2) == NOW + timedelta(minutes=240)


def test_a_gentler_policy_is_a_configuration_change_not_a_code_change():
    """The numbers live in settings because "how long to leave a site alone" is an operational
    decision, and one that will be made in the middle of an incident."""
    gentle = QuarantinePolicy(threshold=2, base_minutes=15, backoff_factor=2.0, max_minutes=60)

    assert gentle.should_quarantine(2) is True
    assert gentle.duration_for(1) == timedelta(minutes=15)
    assert gentle.duration_for(2) == timedelta(minutes=30)
    assert gentle.duration_for(5) == timedelta(minutes=60)
