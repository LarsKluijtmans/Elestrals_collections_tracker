"""The dry run and the commit — stories 028 and 029.

Two guarantees, and they are the reason this bolt is worth its size.

**The dry run writes nothing to the collection.** It writes `import_jobs` and `import_rows` — the
job's own state — and touches `inventory_items` not at all. Story 028 asks for this explicitly, and
`test_a_dry_run_writes_nothing_to_the_collection` asserts it from the outside.

**The commit is one transaction.** One bad row on line 900 means nothing is written, not 899 rows
written and a apology. And every write goes through `InventoryService` rather than the repository,
so imported rows obey the same merge-on-duplicate and completion recompute that hand-entered rows
do. Bypassing the service would let an import produce a collection state the UI cannot.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.import_job import ImportJob, ImportRow
from ..models.inventory_item import CONDITIONS
from .import_matcher import ImportMatcher
from .import_parser import ImportTooLarge, parse, suggest_mapping
from .inventory_service import InventoryError, InventoryService

DEFAULT_CONDITION = "near_mint"
MAX_QUANTITY = 10_000


class JobNotFound(InventoryError):
    code = "import_job_not_found"
    status = 404


class JobNotReady(InventoryError):
    code = "import_job_not_ready"
    status = 409


class ImportRefused(InventoryError):
    code = "bad_request"
    status = 400


@dataclass(frozen=True, slots=True)
class CommitResult:
    added: int
    updated: int
    skipped: int
    rows: int


class ImportService:
    def __init__(self, db: Session, inventory: InventoryService) -> None:
        self._db = db
        self._inventory = inventory

    # --- upload and dry run ----------------------------------------------------------

    def start(self, user_sub: str, *, filename: str, raw: bytes) -> ImportJob:
        """Parse the upload, suggest a mapping, and run the diff.

        Mapping and dry run happen together because a suggested mapping the user has not seen the
        consequences of is not information. The mapping stays editable — `remap` re-runs the diff
        — and story 028's sixth criterion is precisely that a *wrong* mapping's nonsense shows up
        here rather than after the commit.
        """
        try:
            parsed = parse(raw)
        except ImportTooLarge as exc:
            raise ImportRefused(str(exc)) from None

        if not parsed.headers:
            raise ImportRefused("that file has no header row")
        if not parsed.rows:
            raise ImportRefused("that file has a header and no data rows")

        job = ImportJob(
            user_sub=user_sub,
            filename=filename[:255],
            status="mapping",
            encoding=parsed.encoding,
            delimiter=parsed.delimiter,
            mapping=suggest_mapping(parsed.headers),
            total_rows=len(parsed.rows),
        )
        self._db.add(job)
        self._db.flush()

        for line_number, cells in parsed.rows:
            self._db.add(ImportRow(job_id=job.id, line_number=line_number, raw=cells))
        self._db.commit()

        return self.dry_run(user_sub, job.id)

    def remap(self, user_sub: str, job_id: str, mapping: dict[str, str]) -> ImportJob:
        job = self.get(user_sub, job_id)
        if job.status == "committed":
            raise JobNotReady("that import has already been committed")
        job.mapping = {k: v for k, v in mapping.items() if v}
        self._db.commit()
        return self.dry_run(user_sub, job_id)

    def dry_run(self, user_sub: str, job_id: str) -> ImportJob:
        """Resolve every row against the catalog and the caller's collection. **No writes.**

        The matcher's index is built once for the whole job rather than per row — a 5,000-row file
        against a 5,000-card catalog would otherwise re-read the catalog 5,000 times, which is the
        difference between the 30-second budget and several minutes.
        """
        job = self.get(user_sub, job_id)
        if job.status == "committed":
            raise JobNotReady("that import has already been committed")

        matcher = ImportMatcher(self._db)
        owned = self._owned_printings(user_sub)
        counts = {"add": 0, "update": 0, "needs_confirmation": 0, "rejected": 0}

        for row in job.rows:
            values = self._mapped(job.mapping, row.raw)
            self._resolve(row, values, matcher, owned)
            counts[row.verdict] += 1

        job.add_count = counts["add"]
        job.update_count = counts["update"]
        job.needs_confirmation_count = counts["needs_confirmation"]
        job.rejected_count = counts["rejected"]
        job.status = "ready"
        self._db.commit()
        return job

    def confirm_rows(self, user_sub: str, job_id: str, row_ids: list[str]) -> ImportJob:
        """Accept specific fuzzy matches. **Per row, never in bulk by default.**

        Story 028: fuzzy matches are not included unless confirmed individually. A "confirm all"
        button would collapse the whole point of rung 4 into one click somebody makes without
        reading — so this takes a list of ids the UI built from rows the user actually ticked.
        """
        job = self.get(user_sub, job_id)
        if job.status == "committed":
            raise JobNotReady("that import has already been committed")

        wanted = set(row_ids)
        for row in job.rows:
            if row.id in wanted and row.verdict == "needs_confirmation":
                row.confirmed = True
        self._db.commit()
        return job

    # --- commit ----------------------------------------------------------------------

    def commit(self, user_sub: str, job_id: str) -> CommitResult:
        """Apply the job. **One transaction: all of it, or none of it.**

        Row 900 failing means rows 1–899 are rolled back with it. That is story 029's second
        criterion and it is the right trade for an import: a half-applied spreadsheet leaves a
        collection in a state the user cannot reason about and cannot easily undo, whereas a failed
        import leaves them exactly where they started with a reason.

        Writes go through `InventoryService`, so merge-on-duplicate and the completion recompute
        apply identically to imported and hand-entered rows.
        """
        job = self.get(user_sub, job_id)
        if job.status == "committed":
            raise JobNotReady("that import has already been committed")
        if job.status != "ready":
            raise JobNotReady("run the dry run before committing")

        applicable = [
            row for row in job.rows
            if row.verdict in ("add", "update")
            or (row.verdict == "needs_confirmation" and row.confirmed)
        ]
        skipped = len(job.rows) - len(applicable)

        added = updated = 0
        failed_line: int | None = None
        try:
            # `atomic()` suspends the service's per-write commits, so the whole import is one
            # transaction. Without it, `InventoryService.add` commits after every row and a
            # failure on line 900 leaves 899 rows written — which is precisely what story 029's
            # second criterion forbids, and precisely what the first version of this did.
            with self._inventory.atomic():
                for row in applicable:
                    failed_line = row.line_number
                    result = self._inventory.add(
                        user_sub,
                        printing_id=row.printing_id,
                        condition=row.condition or DEFAULT_CONDITION,
                        quantity=row.quantity or 1,
                    )
                    if result.merged:
                        updated += 1
                    else:
                        added += 1
        except Exception as exc:  # noqa: BLE001 — re-raised as ImportRefused below
            # Everything rolls back, including the rows that succeeded. A partially imported
            # spreadsheet is worse than a failed one: the user cannot tell what landed and cannot
            # easily undo it. A failure leaves them exactly where they started, with a reason.
            self._db.rollback()
            job = self.get(user_sub, job_id)
            job.status = "failed"
            job.error_summary = f"{type(exc).__name__}: {exc}"[:2000]
            self._db.commit()
            raise ImportRefused(
                f"nothing was imported — row {failed_line} failed: {exc}"
            ) from None

        job.status = "committed"
        self._db.commit()
        return CommitResult(added=added, updated=updated, skipped=skipped, rows=len(applicable))

    # --- reads -----------------------------------------------------------------------

    def get(self, user_sub: str, job_id: str) -> ImportJob:
        job = self._db.scalar(
            select(ImportJob).where(
                ImportJob.user_sub == user_sub, ImportJob.id == job_id
            )
        )
        if job is None:
            raise JobNotFound(job_id)
        return job

    def list_for_user(self, user_sub: str, *, limit: int = 20) -> list[ImportJob]:
        return list(
            self._db.scalars(
                select(ImportJob)
                .where(ImportJob.user_sub == user_sub)
                .order_by(ImportJob.created_at.desc())
                .limit(limit)
            )
        )

    def delete(self, user_sub: str, job_id: str) -> None:
        job = self.get(user_sub, job_id)
        self._db.delete(job)
        self._db.commit()

    # --- internals -------------------------------------------------------------------

    @staticmethod
    def _mapped(mapping: dict, raw: dict) -> dict[str, str]:
        """`{our_field: value}` from `{our_field: their_header}` and `{their_header: value}`."""
        return {
            field: (raw.get(header) or "").strip()
            for field, header in mapping.items()
            if header
        }

    def _owned_printings(self, user_sub: str) -> set[str]:
        from ..models.inventory_item import InventoryItem

        return set(self._db.scalars(
            select(InventoryItem.printing_id).where(InventoryItem.user_sub == user_sub)
        ))

    def _resolve(
        self, row: ImportRow, values: dict[str, str],
        matcher: ImportMatcher, owned: set[str],
    ) -> None:
        quantity, quantity_error = self._quantity(values)
        if quantity_error:
            row.verdict, row.match_rung, row.reason = "rejected", "none", quantity_error
            row.printing_id = row.quantity = row.condition = None
            return

        condition, condition_error = self._condition(values)
        if condition_error:
            row.verdict, row.match_rung, row.reason = "rejected", "none", condition_error
            row.printing_id = row.quantity = row.condition = None
            return

        match = matcher.match(values)
        row.match_rung = match.rung
        row.match_score = match.score
        row.printing_id = match.printing_id
        row.quantity = quantity
        row.condition = condition

        if not match.matched:
            row.verdict, row.reason = "rejected", match.reason
            return

        row.reason = None
        if match.needs_confirmation:
            # Rung 4. Not counted as an add, not applied, until a human ticks it.
            row.verdict = "needs_confirmation"
        elif match.printing_id in owned:
            row.verdict = "update"
        else:
            row.verdict = "add"

    @staticmethod
    def _quantity(values: dict[str, str]) -> tuple[int, str | None]:
        """Parse the quantity column, and say clearly when it is not one.

        This is where story 028's sixth criterion surfaces: mis-map quantity onto the
        collector-number column and every row rejects with *"'BS1-001' is not a quantity"* — which
        is the dry run doing exactly the job it exists for.
        """
        raw = (values.get("quantity") or "").strip()
        if not raw:
            return 1, None
        try:
            quantity = int(float(raw.replace(",", ".")))
        except ValueError:
            return 0, f"{raw!r} is not a quantity — check the column mapping"
        if quantity < 1:
            return 0, f"quantity {quantity} is not a number of cards to own"
        if quantity > MAX_QUANTITY:
            return 0, f"quantity {quantity} is above the {MAX_QUANTITY:,} limit"
        return quantity, None

    @staticmethod
    def _condition(values: dict[str, str]) -> tuple[str, str | None]:
        raw = (values.get("condition") or "").strip().lower().replace(" ", "_").replace("-", "_")
        if not raw:
            return DEFAULT_CONDITION, None
        # The abbreviations every collector spreadsheet uses, mapped rather than rejected.
        shorthand = {
            "m": "mint", "nm": "near_mint", "lp": "lightly_played", "ex": "lightly_played",
            "mp": "moderately_played", "hp": "heavily_played", "dmg": "damaged",
            "d": "damaged", "gd": "moderately_played", "good": "moderately_played",
        }
        resolved = shorthand.get(raw, raw)
        if resolved not in CONDITIONS:
            return DEFAULT_CONDITION, f"{raw!r} is not a condition we recognise"
        return resolved, None
