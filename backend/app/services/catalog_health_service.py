"""Catalog health for the operator console — story 034.

Answers one question: *can I trust what the catalog currently says?* Three signals do that —
how long since each source last succeeded, which sets are short of their declared size, and
what the last run refused to import.

Staleness thresholds are configuration rather than numbers baked into a template, because
"stale" for a hand-maintained seed is not "stale" for a nightly scraper.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..config import settings
from ..importer.sources import SOURCES
from ..repositories.card_repository import CardRepository
from ..repositories.catalog_import_repository import CatalogImportRepository
from ..repositories.set_repository import SetRepository
from ..schemas import (
    CatalogHealth,
    RejectionRollupModel,
    SetCoverageModel,
    SourceHealth,
    StalenessModel,
)


def classify(last_success_at: datetime | None, *, now: datetime | None = None) -> StalenessModel:
    if last_success_at is None:
        # A first-class state. Returning `fresh` with a null date would read as healthy.
        return StalenessModel(last_success_at=None, age_hours=None, state="never_run")

    now = now or datetime.now(timezone.utc)
    if last_success_at.tzinfo is None:
        last_success_at = last_success_at.replace(tzinfo=timezone.utc)

    age_hours = max(0.0, (now - last_success_at).total_seconds() / 3600)
    if age_hours >= settings.catalog_stale_after_hours:
        state = "stale"
    elif age_hours >= settings.catalog_ageing_after_hours:
        state = "ageing"
    else:
        state = "fresh"
    return StalenessModel(
        last_success_at=last_success_at, age_hours=round(age_hours, 2), state=state
    )


class CatalogHealthService:
    def __init__(
        self,
        imports: CatalogImportRepository,
        sets: SetRepository,
        cards: CardRepository,
    ) -> None:
        self._imports = imports
        self._sets = sets
        self._cards = cards

    def health(self) -> CatalogHealth:
        latest_by_source = {run.source: run for run in self._imports.latest_per_source()}

        sources: list[SourceHealth] = []
        # Iterate the *registry*, not the run table: a source that has never run is exactly
        # the one an operator needs to see, and it has no rows to be found by.
        for name in sorted(SOURCES):
            descriptor = SOURCES[name].describe()
            run = latest_by_source.get(name)
            last_success = run.finished_at if run and run.status == "success" else None
            sources.append(SourceHealth(
                source=name,
                display_name=descriptor.display_name,
                requires_network=descriptor.requires_network,
                last_run_id=run.id if run else None,
                last_status=run.status if run else None,
                last_started_at=run.started_at if run else None,
                staleness=classify(last_success),
            ))

        below: list[SetCoverageModel] = []
        for set_row, imported in self._sets.summaries():
            if set_row.card_count and imported < set_row.card_count:
                below.append(SetCoverageModel(
                    set_code=set_row.code,
                    expected=set_row.card_count,
                    imported=imported,
                    missing_count=set_row.card_count - imported,
                ))

        newest = max(
            latest_by_source.values(), key=lambda r: r.started_at, default=None
        )
        rejections = [
            RejectionRollupModel(reason_code=code, count=count, example_source_ref=example)
            for code, count, example in (
                self._imports.rejection_rollup(newest.id) if newest else []
            )
        ]

        return CatalogHealth(
            sources=sources,
            sets_below_coverage=below,
            latest_run_id=newest.id if newest else None,
            rejections=rejections,
        )
