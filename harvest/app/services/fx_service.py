"""FX normalisation — story 018.

**The rate for the observation's own day, never today's.** Using today's rate for a year-old sale
rewrites history every morning: the same past day's value moves because the euro moved, and a
portfolio chart then shows movement that never happened. That is the same failure story 022 refuses
when it values a past snapshot with that day's rollups, and it is worth noticing that the two
stories arrived at the identical rule independently.

**Conversion is a join, not a call.** `fx_rates` is `(day, base, quote) → rate`, fetched once a day
by a scheduled job. Nothing in a request path talks to a rate provider.

**Carry-forward is marked, not silent.** A missing day uses the previous rate and flags the result
approximate — an approximate conversion over a weekend is fine, and one over a fortnight is a broken
job that the flag makes visible instead of quietly wrong numbers.

**Money never becomes a float.** Cents in, cents out, with an explicit currency at both ends. The
rate is `Decimal` throughout and rounding happens once, at the end.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.fx_rate import FxRate

#: How far back a missing rate may be carried. Beyond this, conversion **fails** rather than
#: quietly using a month-old number: at that distance the flag stops being a caveat and starts
#: being an excuse.
MAX_CARRY_FORWARD_DAYS = 14


class NoRateAvailable(LookupError):
    """No rate for this pair within the carry-forward window. The caller leaves the figure in its
    original currency rather than inventing one."""


@dataclass(frozen=True, slots=True)
class Converted:
    cents: int
    currency: str
    #: The original, kept alongside. Story 018: the source amount stays visible on the record — a
    #: converted figure with no way back to what was actually paid is unauditable.
    original_cents: int
    original_currency: str
    rate: Decimal
    rate_day: date
    #: True when the rate came from an earlier day than the amount.
    approximate: bool


class FxService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def rate_for(self, day: date, base: str, quote: str) -> tuple[Decimal, date, bool]:
        """`(rate, the day it is actually from, whether it was carried forward)`.

        Same-currency pairs short-circuit to 1 without touching the table — otherwise every
        EUR→EUR conversion would need a row that has no business existing.
        """
        base, quote = base.upper(), quote.upper()
        if base == quote:
            return Decimal(1), day, False

        exact = self._db.scalar(
            select(FxRate).where(
                FxRate.day == day, FxRate.base == base, FxRate.quote == quote,
            )
        )
        if exact is not None:
            return Decimal(str(exact.rate)), exact.day, exact.is_carried_forward

        # The most recent rate at or before the day, within the window. Ordered rather than
        # looped a day at a time: a fortnight of `SELECT`s to find one row is a query pattern
        # that looks fine at ten observations and not at fifty thousand.
        earlier = self._db.scalar(
            select(FxRate)
            .where(
                FxRate.base == base,
                FxRate.quote == quote,
                FxRate.day <= day,
                FxRate.day >= day - timedelta(days=MAX_CARRY_FORWARD_DAYS),
            )
            .order_by(FxRate.day.desc())
            .limit(1)
        )
        if earlier is None:
            raise NoRateAvailable(
                f"no {base}->{quote} rate for {day} or the {MAX_CARRY_FORWARD_DAYS} days before it"
            )
        return Decimal(str(earlier.rate)), earlier.day, True

    def convert(
        self, cents: int, *, day: date, base: str, quote: str,
    ) -> Converted:
        """Convert an amount using the rate for **its own day**.

        Rounding is `ROUND_HALF_UP` at the very end, once. Rounding mid-calculation, or letting a
        float in, is how a total stops matching the sum of its parts — which a collector notices
        immediately and cannot explain.
        """
        rate, rate_day, carried = self.rate_for(day, base, quote)
        converted = (Decimal(cents) * rate).quantize(Decimal(1), rounding=ROUND_HALF_UP)

        return Converted(
            cents=int(converted),
            currency=quote.upper(),
            original_cents=cents,
            original_currency=base.upper(),
            rate=rate,
            rate_day=rate_day,
            approximate=carried or rate_day != day,
        )

    def store(
        self, day: date, rates: dict[tuple[str, str], Decimal], *,
        carried_forward: bool = False,
    ) -> int:
        """Upsert a day's rates. Idempotent, so the daily job is safe to re-run.

        `(day, base, quote)` is the primary key, so a second fetch for the same day corrects the
        stored rate rather than adding a second opinion about it.
        """
        written = 0
        for (base, quote), rate in rates.items():
            existing = self._db.get(FxRate, (day, base.upper(), quote.upper()))
            if existing is None:
                self._db.add(FxRate(
                    day=day, base=base.upper(), quote=quote.upper(),
                    rate=rate, is_carried_forward=carried_forward,
                ))
            else:
                existing.rate = rate
                existing.is_carried_forward = carried_forward
            written += 1
        self._db.commit()
        return written

    def carry_forward(self, day: date) -> int:
        """Copy the previous available rates onto a day the provider could not be reached for.

        Called by the daily job when a fetch fails, so the gap is filled *and flagged* rather than
        left for `rate_for` to paper over invisibly. The distinction matters: a carried rate
        stored explicitly shows up in the table where somebody can see the job has been failing.
        """
        latest_day = self._db.scalar(
            select(FxRate.day).where(FxRate.day < day).order_by(FxRate.day.desc()).limit(1)
        )
        if latest_day is None:
            return 0

        previous = list(self._db.scalars(select(FxRate).where(FxRate.day == latest_day)))
        return self.store(
            day,
            {(row.base, row.quote): Decimal(str(row.rate)) for row in previous},
            carried_forward=True,
        )
