"""All database access for `price_sources`, including quarantine state.

`enable()` is the only write path that flips the switch, and it refuses without both a terms
review note and a named risk owner. The CHECK constraint says the same thing at the schema level;
both exist because they fail at different moments. The constraint catches a hand-written `UPDATE`
in a console at 2am; this catches it in code, with a message that says what to do about it.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..harvest.quarantine import QuarantinePolicy
from ..models.price_source import PriceSource


class RiskAcceptanceRequired(ValueError):
    """FR-1 under ADR-004, refused in Python before the database refuses it in SQL."""


class PriceSourceRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def by_key(self, key: str) -> PriceSource | None:
        return self._db.scalar(select(PriceSource).where(PriceSource.key == key))

    def get(self, source_id: str) -> PriceSource | None:
        return self._db.get(PriceSource, source_id)

    def list_all(self) -> list[PriceSource]:
        return list(self._db.scalars(select(PriceSource).order_by(PriceSource.key)))

    def list_enabled(self) -> list[PriceSource]:
        return list(
            self._db.scalars(
                select(PriceSource).where(PriceSource.enabled.is_(True)).order_by(PriceSource.key)
            )
        )

    def ensure(
        self,
        key: str,
        *,
        name: str,
        base_url: str,
        access_mode: str,
        reports_sold: bool,
    ) -> PriceSource:
        """Create the row for a registered connector if it has none — **disabled, no note**.

        Deliberately not a way to enable anything. A registered connector with no row produces a
        confusing "source not configured" error; a disabled, note-less row produces the right
        error, which is "nobody has read this source's terms or accepted the risk yet".
        """
        existing = self.by_key(key)
        if existing is not None:
            return existing
        row = PriceSource(
            key=key, name=name, base_url=base_url, access_mode=access_mode,
            enabled=False, reports_sold=reports_sold,
        )
        self._db.add(row)
        self._db.commit()
        return row

    def enable(
        self,
        key: str,
        *,
        note: str | None = None,
        accepted_by: str | None = None,
        robots_checked_on: date | None = None,
    ) -> PriceSource:
        row = self.by_key(key)
        if row is None:
            raise LookupError(f"No price source {key!r}")
        if note is not None:
            row.tos_review_note = note.strip()
        if accepted_by is not None:
            row.risk_accepted_by = accepted_by.strip()
            row.risk_accepted_on = date.today()

        if not (row.tos_review_note or "").strip():
            raise RiskAcceptanceRequired(
                f"Source {key!r} cannot be enabled without a terms review note. Under ADR-004 "
                "the note is not a permission slip — it is the record of what was accepted, and "
                "'reviewed: yes' is not one."
            )
        if not (row.risk_accepted_by or "").strip():
            raise RiskAcceptanceRequired(
                f"Source {key!r} cannot be enabled without `risk_accepted_by`. ADR-004 accepts a "
                "contractual risk per source; a person has to be attached to that acceptance."
            )

        row.enabled = True
        if robots_checked_on is not None:
            row.robots_checked_on = robots_checked_on
        self._db.commit()
        return row

    def disable(self, key: str) -> PriceSource:
        """The kill switch. Takes effect on the next scan, with no deploy."""
        row = self.by_key(key)
        if row is None:
            raise LookupError(f"No price source {key!r}")
        row.enabled = False
        self._db.commit()
        return row

    # --- quarantine (FR-18) ---------------------------------------------------------

    def quarantine(
        self,
        row: PriceSource,
        *,
        reason: str,
        policy: QuarantinePolicy,
        now: datetime | None = None,
    ) -> PriceSource:
        """Escalate one level and stop asking until the backoff expires."""
        now = now or datetime.now(timezone.utc)
        row.quarantine_level = (row.quarantine_level or 0) + 1
        row.quarantined_until = policy.until(now, row.quarantine_level)
        row.quarantine_reason = reason[:255]
        self._db.commit()
        return row

    def clear_quarantine(self, row: PriceSource, *, reset_level: bool = True) -> PriceSource:
        """A clean run releases the source, and resets the escalation.

        Resetting matters: without it a source that was blocked once in March starts its next
        quarantine at sixteen hours, which punishes it for having recovered.
        """
        row.quarantined_until = None
        row.quarantine_reason = None
        if reset_level:
            row.quarantine_level = 0
        self._db.commit()
        return row

    def due_for_probe(self, *, now: datetime | None = None) -> list[PriceSource]:
        """Enabled sources whose quarantine has expired — one probing request each.

        Deliberately *not* "resume the full scan": a 400-query deep run against a source that is
        still blocking would re-trigger whatever caused the block.
        """
        now = now or datetime.now(timezone.utc)
        return list(self._db.scalars(
            select(PriceSource).where(
                PriceSource.enabled.is_(True),
                PriceSource.quarantined_until.is_not(None),
                PriceSource.quarantined_until <= now,
            )
        ))
