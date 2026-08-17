"""What we tell people about our conduct has to match what we do.

`/api/v1/health` publishes a `conduct` block. Under ADR-004 this harvester does not consult
robots.txt, and the honest value there is `false` — a scraper that says so is one a site owner can
make an informed decision about.

The flag behind it, `harvest_obey_robots`, is read *only* by the health endpoint and the startup
log. Nothing in the request path consults it. So setting it true would change the claim and not the
behaviour, which is the one outcome worse than the current `false`: an untrue statement of good
conduct, published at the exact URL somebody checks to find out whether a bot is behaving.

These tests pin that the flag cannot be turned into a lie.
"""
from __future__ import annotations

import pytest

from app.config import Settings, settings


def test_the_flag_is_false_and_the_disclosure_is_therefore_honest():
    assert settings.harvest_obey_robots is False


def test_enabling_the_flag_is_refused_rather_than_believed():
    """**The point of the module.**

    Accepting `true` here would publish `"obeys_robots_txt": true` from a harvester that ignores
    robots.txt entirely. Refusing to start is the honest failure.
    """
    with pytest.raises(ValueError) as caught:
        Settings(harvest_obey_robots=True)

    assert "not implemented" in str(caught.value)


def test_the_refusal_says_what_would_have_to_be_built():
    """An error that only says "no" gets worked around. This one has to point at the work.

    If somebody genuinely wants robots.txt honoured, the message should send them to
    `PoliteClient` rather than to the line that raised.
    """
    with pytest.raises(ValueError) as caught:
        Settings(harvest_obey_robots=True)

    message = str(caught.value)
    assert "PoliteClient" in message
    assert "robots.txt" in message


def test_nothing_in_the_request_path_reads_the_flag():
    """A guard on the guard.

    The validator above is only correct while the flag remains a pure disclosure. The moment
    somebody wires it into `PoliteClient` for real, this test fails — which is the signal to delete
    the validator, not to weaken this assertion.

    Scoped to the harvesting package rather than the whole app, because the health controller and
    `main` legitimately read it in order to report it.
    """
    import pathlib

    harvest_pkg = pathlib.Path(__file__).parent.parent / "app" / "harvest"
    readers = [
        path.name
        for path in harvest_pkg.rglob("*.py")
        if "harvest_obey_robots" in path.read_text(encoding="utf-8")
    ]

    assert readers == [], (
        f"{readers} now read harvest_obey_robots. If robots.txt is genuinely honoured, remove "
        "validate_robots_flag from config.py so the flag can be set — and update ADR-004."
    )


def test_health_reports_the_flag_rather_than_a_constant():
    """The disclosure has to track the setting, not a literal typed next to it.

    A hardcoded `false` in the health controller would read identically today and would drift the
    moment anybody implemented the check — the endpoint would keep saying "we ignore robots.txt"
    after it had stopped being true. Reporting is the *only* legitimate use of this flag, so the
    one thing worth asserting about it is that the reporting is wired to the value.
    """
    from app.controllers import health

    source = __import__("inspect").getsource(health)
    assert "settings.harvest_obey_robots" in source, (
        "the health endpoint should report the configured value, not a literal"
    )


def test_the_conduct_block_names_both_halves():
    """`identified` sits next to `obeys_robots_txt`, and the pairing is the honest bit.

    One is enforced — `HarvestGate` refuses to run any source when the contact address is empty,
    which `test_harvest_gate.py` covers — and one is a disclosure with nothing behind it. Publishing
    both together is what lets a reader tell how this harvester behaves without reading ADR-004.
    """
    from app.controllers import health

    source = __import__("inspect").getsource(health)
    assert "obeys_robots_txt" in source
    assert "identified" in source
