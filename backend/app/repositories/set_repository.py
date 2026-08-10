"""All database access for `sets`."""
from __future__ import annotations

from datetime import date

from sqlalchemy import String, func, select
from sqlalchemy.orm import Session

from ..models.card import Card
from ..models.set import Set

#: Sorting sentinel for sets with no release date. Explicit rather than relying on how a given
#: engine orders NULLs, which differs between MySQL and SQLite.
_UNDATED = "1900-01-01"


class SetRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_code(self, code: str) -> Set | None:
        return self._db.scalar(select(Set).where(Set.code == code))

    def list_all(self) -> list[Set]:
        return list(self._db.scalars(select(Set).order_by(Set.code)))

    def summaries(self, *, series: str | None = None) -> list[tuple[Set, int]]:
        """Every set with the number of cards actually imported, in **one** query.

        Counting per set in a loop would be 30 queries today and a habit later; the imported
        count is also what makes a shortfall against the declared `card_count` visible on the
        gallery rather than only in an import report.
        """
        stmt = (
            select(Set, func.count(Card.id))
            .outerjoin(Card, Card.set_id == Set.id)
            .group_by(Set.id)
            .order_by(
                func.coalesce(Set.released_on, func.cast(_UNDATED, String)).desc(),
                Set.code.asc(),
            )
        )
        if series:
            stmt = stmt.where(Set.series == series)
        return [(row[0], int(row[1] or 0)) for row in self._db.execute(stmt).all()]

    def upsert(
        self,
        *,
        code: str,
        name: str,
        card_count: int,
        series: str | None = None,
        released_on: date | None = None,
        logo_asset_url: str | None = None,
    ) -> Set:
        """`card_count` is the declared printed size. It is written from the source's
        declaration and never from a count of imported rows."""
        row = self.get_by_code(code)
        if row is None:
            row = Set(code=code, name=name, card_count=card_count, series=series,
                      released_on=released_on, logo_asset_url=logo_asset_url)
            self._db.add(row)
            self._db.commit()
            return row

        incoming = (name, card_count, series, released_on, logo_asset_url)
        current = (row.name, row.card_count, row.series, row.released_on, row.logo_asset_url)
        if incoming == current:
            # Same rule as cards and printings: unchanged means no write. Otherwise every
            # re-import touches every set row for nothing.
            return row

        row.name, row.card_count, row.series = name, card_count, series
        row.released_on, row.logo_asset_url = released_on, logo_asset_url
        self._db.commit()
        return row
