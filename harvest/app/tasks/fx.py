"""The daily FX fetch — story 018's job half.

**One call a day.** Nothing in a request path talks to a rate provider; conversion is a join
against `fx_rates`, which this fills. A per-request lookup would put a third party in the latency
path of every price a collector looks at, and in the failure path of every one of them too.

**A failed fetch carries forward and says so.** The gap is filled with the previous day's rates and
the rows are stored with `is_carried_forward = True`, so the table itself shows the job has been
failing. Leaving the gap for `rate_for` to paper over would work and would be invisible — and an
approximate conversion nobody can see is indistinguishable from an accurate one.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from ..config import settings
from ..core.db import SessionLocal
from ..services.fx_service import FxService
from ..services.logging_service import log_event
from .celery_app import celery_app

#: The currencies observations actually arrive in. Kept short deliberately: every pair is a row a
#: day forever, and a currency nobody sells in is a row nobody reads.
QUOTES = ("EUR", "USD", "GBP", "JPY")

#: A free, keyless daily-rates endpoint. Swapping providers means changing this and `_parse`; the
#: storage shape and everything downstream are provider-agnostic on purpose.
PROVIDER_URL = "https://api.frankfurter.app/{day}?from={base}&to={to}"


@celery_app.task(name="harvest.fx")
def fetch_rates(day: str | None = None) -> dict:
    """Fetch and store one day's rates.

    Runs on the beat schedule, and is safe to run by hand or twice: `(day, base, quote)` is the
    primary key, so a re-fetch corrects a stored rate rather than adding a second opinion.
    """
    target = date.fromisoformat(day) if day else date.today() - timedelta(days=1)
    base = settings.harvest_base_currency
    quotes = [q for q in QUOTES if q != base]

    db = SessionLocal()
    fx = FxService(db)
    try:
        try:
            rates = _fetch(target, base, quotes)
        except Exception as exc:  # noqa: BLE001 — any provider failure carries forward
            carried = fx.carry_forward(target)
            log_event(
                "warning",
                f"fx fetch failed for {target}; carried {carried} rate(s) forward",
                component="fx", operation="fetch",
                context={"day": target.isoformat(), "error": f"{type(exc).__name__}: {exc}"},
            )
            return {"day": target.isoformat(), "fetched": 0, "carried_forward": carried}

        written = fx.store(target, rates)
        log_event(
            "info", f"fx rates stored for {target}",
            component="fx", operation="fetch",
            context={"day": target.isoformat(), "pairs": written},
        )
        return {"day": target.isoformat(), "fetched": written, "carried_forward": 0}
    finally:
        db.close()


def _fetch(day: date, base: str, quotes: list[str]) -> dict[tuple[str, str], Decimal]:
    """One request. Both directions are stored from it — `A→B` and its reciprocal — so a
    conversion never has to decide whether to invert a rate at the call site.

    Plain `httpx` rather than `PoliteClient`: this is a published JSON API being used as intended,
    not a site being scraped over its objection. The rate limiting, host pinning and block
    detection that wrap a scraper are the wrong shape here, and dressing an ordinary API call in
    them would blur the distinction ADR-004 rests on.
    """
    import httpx

    with httpx.Client(timeout=15.0) as client:
        response = client.get(
            PROVIDER_URL.format(day=day.isoformat(), base=base, to=",".join(quotes))
        )
        response.raise_for_status()
        payload = response.json()

    out: dict[tuple[str, str], Decimal] = {}
    for quote, value in (payload.get("rates") or {}).items():
        # `Decimal(str(...))` rather than `Decimal(float)`: the latter carries the float's binary
        # approximation into a value money is computed from.
        rate = Decimal(str(value))
        if rate <= 0:
            continue
        out[(base, quote)] = rate
        out[(quote, base)] = Decimal(1) / rate
    return out
