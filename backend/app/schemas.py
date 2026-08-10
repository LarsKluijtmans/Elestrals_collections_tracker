"""Pydantic request/response models at the API boundary."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """The one error shape. Never a bare `detail` string from business logic."""
    error: ErrorBody


class ProfileResponse(BaseModel):
    user_sub: str
    handle: str | None
    collection_visibility: Literal["private", "link", "public"]
    default_currency: str
    condition_scale: Literal["tcg", "cardmarket"]
    # Platform-owned; read-only here, edited in the platform's own /account.
    email: str | None
    username: str | None
    enriched: bool


class ProfilePatch(BaseModel):
    handle: str | None = Field(default=None, min_length=3, max_length=32,
                               pattern=r"^[a-zA-Z0-9_-]+$")
    collection_visibility: Literal["private", "link", "public"] | None = None
    default_currency: str | None = Field(default=None, min_length=3, max_length=3)
    condition_scale: Literal["tcg", "cardmarket"] | None = None


class ClientEvent(BaseModel):
    """A browser-reported event. The browser cannot write to logs-api directly (it has no
    `logs:write`), so events are relayed through here and stamped with the validated caller
    — identity cannot be spoofed."""
    level: Literal["debug", "info", "warning"] = "info"
    message: str = Field(max_length=512)
    component: str | None = Field(default=None, max_length=64)
    context: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    app: str
    database: str


# --- Catalog import reporting (bolt 002, story 009) ---------------------------------

class ImportCountsModel(BaseModel):
    sets_seen: int
    cards_added: int
    cards_updated: int
    #: The success signal of a re-run. Without it, "0 added, 0 updated" is
    #: indistinguishable from "the importer did nothing at all".
    cards_unchanged: int
    printings_added: int
    rejected: int


class CoverageModel(BaseModel):
    """Imported cards against the set's *declared* printed size."""
    set_code: str
    expected: int
    imported: int
    missing_count: int
    #: Named exactly when the numbering is unambiguous; empty means undecidable, not complete.
    missing_numbers: list[str] = Field(default_factory=list)


class RejectionModel(BaseModel):
    source_ref: str
    reason_code: str
    field: str | None
    message: str
    raw_record: dict[str, Any] | None


class PagedRejections(BaseModel):
    items: list[RejectionModel]
    next_cursor: str | None
    total: int


class ImportRunSummary(BaseModel):
    id: str
    source: str
    status: Literal["running", "success", "partial", "failed"]
    started_at: datetime
    finished_at: datetime | None
    counts: ImportCountsModel


class ImportRunDetail(ImportRunSummary):
    coverage: list[CoverageModel] = Field(default_factory=list)
    rejections: PagedRejections
    error_summary: str | None = None


class PagedImportRuns(BaseModel):
    items: list[ImportRunSummary]
    next_cursor: str | None
    total: int


class StartImportRequest(BaseModel):
    source: str = Field(default="csv_seed", max_length=48)
    #: Omit for every set the source declares.
    set_codes: list[str] | None = Field(default=None, max_length=64)
