"""Orchestrates one import run: fetch → normalise → upsert → report.

One execution path, shared by the CLI and the admin endpoint, so the thing an operator
triggers from the console is byte-for-byte the thing that runs on a schedule.

Status semantics, decided in `ddd-02-technical-design.md`:

* **rejections do not change the status.** A run's job is to import what it can and report
  what it could not — that report *is* story 009, not a failure.
* **a set failing outright does.** Some sets in, some failed → `partial`. None in → `failed`.
"""
from __future__ import annotations

from datetime import date

from ..core.redaction import redact
from ..importer.canonical import ImportCounts, Rejection
from ..importer.normaliser import normalise_set
from ..importer.sources import get_source
from ..models.catalog_import import CatalogImport
from ..models.import_rejection import ImportRejection
from ..repositories.card_repository import CardRepository
from ..repositories.catalog_import_repository import CatalogImportRepository
from ..repositories.set_repository import SetRepository
from .catalog_upsert import ADDED, UNCHANGED, UPDATED, CatalogUpsert
from .coverage_service import CoverageService
from .logging_service import log_event


def _parse_date(value: str | None) -> date | None:
    """A release date is a calendar date, not an instant — no timezone belongs here."""
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


class ImportRunner:
    def __init__(
        self,
        *,
        sets: SetRepository,
        cards: CardRepository,
        imports: CatalogImportRepository,
        upsert: CatalogUpsert,
        coverage: CoverageService,
    ) -> None:
        self._sets = sets
        self._cards = cards
        self._imports = imports
        self._upsert = upsert
        self._coverage = coverage

    def run(
        self,
        *,
        source_name: str,
        set_codes: list[str] | None = None,
        run: CatalogImport | None = None,
    ) -> CatalogImport:
        """Execute one run.

        `run` lets the caller create the row first and hand it over — the admin endpoint does
        that so it can return the run id in its `202` before the work finishes. The CLI passes
        nothing and the row is created here. Either way this is the same execution path.
        """
        adapter = get_source(source_name)
        descriptor = adapter.describe()
        targets = set_codes or adapter.available_sets()

        run = run if run is not None else self._imports.start(source_name)
        self._imports.record_targets(run, targets)
        log_event(
            "info", f"catalog import started: {source_name}",
            component="importer", operation="import.start",
            context={"import_id": run.id, "sets": targets,
                     "requires_network": descriptor.requires_network},
        )

        counts = ImportCounts()
        rejections: list[Rejection] = []
        failures: list[str] = []
        succeeded = 0

        for set_code in targets:
            try:
                self._import_one_set(
                    adapter, set_code, counts=counts, rejections=rejections, run_id=run.id
                )
                succeeded += 1
            except Exception as exc:  # noqa: BLE001 — one bad set must not kill the run
                self._cards.rollback()
                failures.append(f"{set_code}: {exc}")
                log_event(
                    "error", f"catalog import failed for set {set_code}",
                    component="importer", operation="import.set", exc=exc,
                    context={"import_id": run.id, "set_code": set_code},
                )

        counts.rejected = len(rejections)
        self._imports.add_rejections(
            run.id, [self._to_row(run.id, r) for r in rejections]
        )

        if failures and succeeded == 0:
            status = "failed"
        elif failures:
            status = "partial"
        else:
            status = "success"

        self._imports.finish(
            run,
            status=status,
            counts=counts.as_dict(),
            error_summary="\n".join(failures) or None,
        )

        log_event(
            "info" if status == "success" else "warning",
            f"catalog import {status}: {source_name}",
            component="importer", operation="import.finish",
            context={"import_id": run.id, "status": status, **counts.as_dict()},
        )
        return run

    def _import_one_set(
        self,
        adapter,
        set_code: str,
        *,
        counts: ImportCounts,
        rejections: list[Rejection],
        run_id: str,
    ) -> None:
        meta = adapter.set_meta(set_code)

        # card_count comes from the source's *declaration*, never from a count of what we
        # imported. This is the whole guard against silent 100% completion.
        set_row = self._sets.upsert(
            code=meta.code,
            name=meta.name,
            card_count=meta.card_count,
            series=meta.series,
            released_on=_parse_date(meta.released_on),
            logo_asset_url=meta.logo_asset_url,
        )
        counts.sets_seen += 1

        result = normalise_set(adapter.fetch(meta.code), set_code=meta.code)
        rejections.extend(result.rejections)

        for card in result.cards:
            outcome = self._upsert.upsert(card, set_id=set_row.id)
            if outcome.outcome == ADDED:
                counts.cards_added += 1
            elif outcome.outcome == UPDATED:
                counts.cards_updated += 1
            elif outcome.outcome == UNCHANGED:
                counts.cards_unchanged += 1
            counts.printings_added += outcome.printings_added

        report = self._coverage.coverage(meta.code)
        if report is not None and not report.is_complete:
            # Reported loudly. Bolt 003's operator console reads the same numbers off the
            # run-detail response rather than recomputing them.
            log_event(
                "warning",
                f"set {meta.code} coverage incomplete: "
                f"{report.imported}/{report.expected} cards",
                component="importer", operation="import.coverage",
                context={"import_id": run_id, **report.as_dict()},
            )

    @staticmethod
    def _to_row(run_id: str, rejection: Rejection) -> ImportRejection:
        return ImportRejection(
            import_id=run_id,
            source_ref=rejection.source_ref,
            # A source file can contain anything, so the raw record goes through the same
            # redaction path as every other persisted context.
            raw_record=redact(rejection.raw_record) if rejection.raw_record else None,
            reason_code=rejection.reason_code,
            field=rejection.field,
            message=rejection.message,
        )
