"""`import_jobs` and `import_rows` — a collection import between its dry run and its commit.

**Persisted, not held in memory.** Story 028 asks for the job to survive leaving the page, and the
reason is plain: a 5,000-row dry run is not something to make someone sit through twice because
they went to check a spreadsheet in another tab. Server memory is also the wrong place to keep an
untrusted 5,000-row upload while a human decides what to do about it.

Note the deliberate naming distance from `catalog_imports`. That table records **our** catalog being
imported from a data source; this one records **a user's collection** being imported from their own
spreadsheet. They share a word and nothing else, and conflating them would put user-uploaded content
in a table an operator console reads.

Every row of the file becomes an `import_rows` row carrying its match verdict and confidence. That
is what makes the diff reviewable, what makes a per-row rejection reason possible, and what lets the
commit be a single transaction over rows that have already been resolved.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base
from .base import TimestampMixin, UuidPrimaryKeyMixin

#: `mapping` → the user is editing the column mapping. `ready` → dry run done, nothing written.
#: `committed` → applied. `failed` → the commit rolled back and said why.
JOB_STATUSES = ("mapping", "ready", "committed", "failed")

#: The matching ladder from story 028, most to least confident. `exact_printing` is our own export
#: round-tripping; `fuzzy_name` is the one that must never apply without per-row confirmation.
MATCH_RUNGS = (
    "exact_printing",     # rung 1 — printing_id matched outright
    "natural_key",        # rung 2 — set + number + finish + language + edition
    "set_and_number",     # rung 3 — set + number, defaults applied
    "fuzzy_name",         # rung 4 — normalised name similarity, needs confirmation
    "none",               # rung 5 — rejected
)

ROW_VERDICTS = ("add", "update", "needs_confirmation", "rejected")


class ImportJob(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "import_jobs"

    user_sub: Mapped[str] = mapped_column(String(36), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="mapping")

    #: What the sniffer found. Reported back so a user who gets a mangled preview can see *why*
    #: — "we read this as CP1252" is a fixable complaint; "it looks wrong" is not.
    encoding: Mapped[str] = mapped_column(String(16), nullable=False, default="utf-8")
    delimiter: Mapped[str] = mapped_column(String(4), nullable=False, default=",")

    #: `{our_field: their_header}`. Suggested by the parser, editable by the user, and the thing
    #: the whole dry run is a check on.
    mapping: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    add_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    update_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    needs_confirmation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_summary: Mapped[str | None] = mapped_column(Text)

    rows = relationship(
        "ImportRow", back_populates="job", cascade="all, delete-orphan", lazy="selectin",
    )

    __table_args__ = (Index("ix_import_jobs_user", "user_sub", "created_at"),)


class ImportRow(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "import_rows"

    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False
    )
    #: 1-based, as the user's spreadsheet numbers them. A rejection reason that says "row 900" has
    #: to mean the row they can see, not an array index.
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)

    #: The raw parsed cells, kept so the diff can show what was actually in the file. Untrusted
    #: throughout — nothing here is ever evaluated, interpolated or executed.
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    verdict: Mapped[str] = mapped_column(String(24), nullable=False, default="rejected")
    match_rung: Mapped[str] = mapped_column(String(24), nullable=False, default="none")
    #: 0–1. Below the floor is a *rejection*, not a low-confidence match: a confident wrong match
    #: silently corrupts a collection somebody has kept for years.
    match_score: Mapped[float | None] = mapped_column(Float)

    printing_id: Mapped[str | None] = mapped_column(String(36))
    quantity: Mapped[int | None] = mapped_column(Integer)
    condition: Mapped[str | None] = mapped_column(String(24))

    #: Why this row was rejected, in words the uploader can act on. Never a stack trace and never
    #: a bare code — "no card matching 'Vipyro' in set BS9" tells them what to fix.
    reason: Mapped[str | None] = mapped_column(String(255))

    #: Set by the user for `fuzzy_name` rows. The commit skips any that stay false.
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    job = relationship("ImportJob", back_populates="rows")

    __table_args__ = (Index("ix_import_rows_job", "job_id", "line_number"),)
