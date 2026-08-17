"""Builds the `CatalogIndex` a harvest run plans and matches against.

Three queries, once per run, **read-only and cross-schema**. This service holds a `SELECT` grant
on exactly four `elestrals` tables and no write grant at all, so the worst a bug here can do is
read something slowly.

The alternative — asking the database per listing title — turns a 1,000-listing scan into 1,000
round trips against a catalog that has not changed since the run started.

Only `is_tracked_for_price` rows. That column exists so phase 2 can stop spending requests on
dead SKUs without deleting catalog history, and the query planner honouring it is what makes it
more than a comment.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..harvest.catalog_index import CatalogIndex, PrintingEntry, SealedEntry, SetEntry
from ..models.catalog import CatalogCard, CatalogPrinting, CatalogSealedProduct, CatalogSet


class CatalogSnapshotRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def build(self) -> CatalogIndex:
        return CatalogIndex(
            printings=self._printings(),
            sealed=self._sealed(),
            sets=self._sets(),
        )

    def _printings(self) -> list[PrintingEntry]:
        rows = self._db.execute(
            select(
                CatalogPrinting.id, CatalogCard.id, CatalogCard.name, CatalogSet.code,
                CatalogSet.name, CatalogCard.collector_number, CatalogPrinting.rarity,
                CatalogPrinting.finish, CatalogPrinting.language, CatalogPrinting.edition,
            )
            .join(CatalogCard, CatalogCard.id == CatalogPrinting.card_id)
            .join(CatalogSet, CatalogSet.id == CatalogCard.set_id)
            .where(CatalogPrinting.is_tracked_for_price.is_(True))
            .order_by(CatalogSet.code, CatalogCard.collector_number)
        ).all()
        return [
            PrintingEntry(
                printing_id=row[0], card_id=row[1], card_name=row[2], set_code=row[3],
                set_name=row[4], collector_number=row[5], rarity=row[6], finish=row[7],
                language=row[8], edition=row[9],
            )
            for row in rows
        ]

    def _sealed(self) -> list[SealedEntry]:
        rows = self._db.execute(
            select(
                CatalogSealedProduct.id, CatalogSealedProduct.name,
                CatalogSealedProduct.kind, CatalogSet.code,
            )
            .join(CatalogSet, CatalogSet.id == CatalogSealedProduct.set_id, isouter=True)
            .where(CatalogSealedProduct.is_tracked_for_price.is_(True))
            .order_by(CatalogSealedProduct.name)
        ).all()
        return [
            SealedEntry(
                sealed_product_id=row[0], name=row[1], kind=row[2], set_code=row[3]
            )
            for row in rows
        ]

    def _sets(self) -> list[SetEntry]:
        rows = self._db.execute(
            select(CatalogSet.code, CatalogSet.name).order_by(CatalogSet.code)
        ).all()
        return [SetEntry(code=row[0], name=row[1]) for row in rows]

    # --- coverage, for the admin analysis view ---------------------------------------

    def tracked_printing_ids(self) -> list[str]:
        """Every printing phase 2 is supposed to be pricing. The denominator of coverage."""
        return list(self._db.scalars(
            select(CatalogPrinting.id).where(CatalogPrinting.is_tracked_for_price.is_(True))
        ))

    def printing_labels(self, printing_ids: list[str]) -> dict[str, dict[str, str]]:
        """`printing_id -> {card, set, number, finish}` for display.

        The admin views hold printing ids from *our* tables and need names from *theirs*; this is
        the one join that crosses, and it is a read.
        """
        if not printing_ids:
            return {}
        rows = self._db.execute(
            select(
                CatalogPrinting.id, CatalogCard.name, CatalogSet.code,
                CatalogCard.collector_number, CatalogPrinting.finish, CatalogPrinting.rarity,
            )
            .join(CatalogCard, CatalogCard.id == CatalogPrinting.card_id)
            .join(CatalogSet, CatalogSet.id == CatalogCard.set_id)
            .where(CatalogPrinting.id.in_(printing_ids))
        ).all()
        return {
            row[0]: {
                "card": row[1], "set_code": row[2], "collector_number": row[3],
                "finish": row[4], "rarity": row[5],
            }
            for row in rows
        }
