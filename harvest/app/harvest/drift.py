"""Selector drift detection — story 010, and the answer to this intent's worst failure mode.

Under ADR-004 a connector *will* break: sites change markup without notice and without telling
anyone. The failure mode is **silence** — zero rows looks exactly like a quiet market, and a
scraper that quietly stops finding anything reports "no sales seen" for months while the product
slowly becomes wrong.

So the whole design of this module is one distinction, stated in the story as its point:

    parsed fine, nothing matched   ≠   could not parse

The first is a real answer about the market. The second is our parser being broken. They produce
identical row counts and must never produce identical verdicts.

A third outcome sits alongside both: **the source was unreachable.** Different problem, different
alert — a third party being down is not our markup going stale, and conflating them means the alert
that matters gets ignored during the next outage.

**And a fourth, which belongs to story 011 rather than here:** a challenge page is a *block*, not
drift. `SourceRefused` is raised by the connector for exactly that, and this module re-labels it
rather than swallowing it into a parse failure.

Deliberately **not** part of the normal test suite. A third party being down must not fail a pull
request, so this runs on a schedule and reports; `pytest -m drift` is opt-in, and the scheduled
Celery task is the real caller.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..harvest.canonical import Query, RawListing
from ..harvest.http import SourceRefused, SourceUnavailable

#: One query per source that is expected to return results on any normal day. Deliberately a
#: broad, long-lived term rather than a specific card: a niche query returning nothing is a real
#: market answer, and this check must not be able to confuse the two.
PROBE_QUERY = Query(text="elestrals", reason="drift-check")

#: How few results is suspicious rather than merely quiet. A structural break usually yields
#: *zero* parsed rows from a page that still has a results container, so this is about
#: distinguishing "the page changed shape" from "this term is unpopular today".
MIN_EXPECTED = 1


class Verdict(str, Enum):
    OK = "ok"
    #: Parsed, but a field the contract promises stopped being found on every row.
    DRIFTED = "drifted"
    #: The page parsed and genuinely contained nothing. A real answer about the market.
    EMPTY = "empty"
    #: Could not parse at all — no results container. Our problem.
    UNPARSEABLE = "unparseable"
    #: A challenge or interstitial. Story 011 owns this; it is a block, not drift.
    BLOCKED = "blocked"
    #: The third party was down. Not our markup, and not an alert about our markup.
    UNREACHABLE = "unreachable"

    @property
    def is_our_problem(self) -> bool:
        """Whether this verdict should page somebody about *our* code.

        `EMPTY`, `BLOCKED` and `UNREACHABLE` are all real states of the world that need no code
        change — which is precisely why they must not be reported as drift.
        """
        return self in (Verdict.DRIFTED, Verdict.UNPARSEABLE)


#: The fields the connector contract promises for every listing. Checked individually, because
#: story 010's fourth criterion is that a failure names **which field stopped being found**, not
#: merely that the count was zero — "title is missing on all 60 rows" points at a selector;
#: "0 results" points at nothing.
REQUIRED_FIELDS = ("external_id", "title", "url", "price_cents", "currency")

#: Only checked on a source that claims to report sales. Asserting it on an asking-price source
#: would fail every run for a source behaving exactly as designed.
SOLD_FIELDS = ("is_sold",)


@dataclass
class DriftReport:
    source: str
    verdict: Verdict
    parsed: int = 0
    #: `{field: how many rows were missing it}`. The actionable half of the report.
    missing_fields: dict[str, int] = field(default_factory=dict)
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.verdict is Verdict.OK

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "verdict": self.verdict.value,
            "parsed": self.parsed,
            "missing_fields": self.missing_fields,
            "detail": self.detail,
            "is_our_problem": self.verdict.is_our_problem,
        }

    def __str__(self) -> str:
        if self.ok:
            return f"{self.source}: ok ({self.parsed} listings parsed, every field present)"
        if self.missing_fields:
            named = ", ".join(
                f"{field_name} missing on {count}/{self.parsed}"
                for field_name, count in sorted(self.missing_fields.items())
            )
            return f"{self.source}: DRIFTED — {named}"
        return f"{self.source}: {self.verdict.value} — {self.detail}"


def check_parsed(
    source_name: str, listings: list[RawListing], *, reports_sold: bool,
) -> DriftReport:
    """Judge an already-parsed result set. **The part with no network in it.**

    Split out from `check_source` so the interesting logic is testable against a fixture without a
    third party being involved — which is the same reason the fixtures exist at all.
    """
    if not listings:
        # Parsed a results container and found nothing in it. Genuinely different from failing to
        # parse, and the story's last criterion is that this module knows the difference.
        return DriftReport(
            source=source_name,
            verdict=Verdict.EMPTY,
            parsed=0,
            detail=(
                "the page parsed but contained no listings. This is a statement about the "
                "market, not about the parser — but if it persists, check the query"
            ),
        )

    fields_to_check = REQUIRED_FIELDS + (SOLD_FIELDS if reports_sold else ())
    missing: dict[str, int] = {}
    for name in fields_to_check:
        absent = sum(1 for listing in listings if not _present(getattr(listing, name, None)))
        if absent:
            missing[name] = absent

    if not missing:
        return DriftReport(source=source_name, verdict=Verdict.OK, parsed=len(listings))

    # A field absent on *some* rows is normal — not every listing has free shipping, and eBay
    # omits a location on some. A field absent on *every* row is a selector that stopped
    # matching, which is the thing worth waking somebody for.
    total_loss = {f: n for f, n in missing.items() if n == len(listings)}
    if total_loss:
        return DriftReport(
            source=source_name,
            verdict=Verdict.DRIFTED,
            parsed=len(listings),
            missing_fields=total_loss,
            detail=(
                "every parsed listing is missing these fields, which means a selector stopped "
                "matching rather than a few listings being unusual"
            ),
        )

    return DriftReport(
        source=source_name,
        verdict=Verdict.OK,
        parsed=len(listings),
        missing_fields=missing,
        detail="some listings are missing optional fields, which is normal",
    )


def check_source(source, *, reports_sold: bool, limit: int = 25) -> DriftReport:
    """Fetch one known query from the live source and judge what comes back.

    Every failure mode is caught and *labelled* rather than raised: this runs on a schedule, and a
    scheduled check that dies on a network blip tells you less than one that says "unreachable".
    """
    name = getattr(source, "name", source.__class__.__name__)
    try:
        listings = list(source.discover(PROBE_QUERY, limit=limit))
    except SourceRefused as exc:
        # A challenge or interstitial. Story 011 owns this, and calling it drift would send
        # somebody to read selectors when the actual problem is that we have been blocked.
        return DriftReport(
            source=name, verdict=Verdict.BLOCKED,
            detail=f"{exc} (this is a block, not drift — see story 011's quarantine)",
        )
    except SourceUnavailable as exc:
        return DriftReport(
            source=name, verdict=Verdict.UNREACHABLE,
            detail=f"{exc} (the source was down; this says nothing about our parser)",
        )
    except Exception as exc:  # noqa: BLE001 — a scheduled check reports, it does not crash
        return DriftReport(
            source=name, verdict=Verdict.UNPARSEABLE,
            detail=f"{type(exc).__name__}: {exc}",
        )

    return check_parsed(name, listings, reports_sold=reports_sold)


def _present(value) -> bool:
    """Whether a field actually carries information.

    `0` and `False` count as present — a free listing is priced at zero and an unsold item is
    legitimately `is_sold=False`. Only `None` and the empty string are absences, which is why this
    is not `bool(value)`.
    """
    return value is not None and value != ""
