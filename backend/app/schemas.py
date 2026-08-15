"""Pydantic request/response models at the API boundary."""
from __future__ import annotations

from datetime import date, datetime
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


# --- Catalog read surface (bolt 003, stories 010-012) --------------------------------
#
# These are read models, not the write schema with fields renamed. They are what a screen
# needs; keeping them separate is what lets the catalog tables change without breaking a
# public contract that is cached for five minutes at a time.

class PrintingView(BaseModel):
    printing_id: str
    rarity: str
    finish: str
    language: str
    edition: str
    image_url: str | None
    #: `"{name} — {set} {rarity}"`, generated centrally. ux-guide §9, binding.
    alt_text: str


class CardSearchResult(BaseModel):
    card_id: str
    name: str
    set_code: str
    collector_number: str
    card_type: str
    element: str | None
    primary_printing: PrintingView | None
    printing_count: int
    #: *Why* this row matched. On the wire so a test can assert the reason rather than pin an
    #: opaque position, and so the UI can explain a surprising hit.
    match_kind: Literal[
        "exact_name", "name_prefix", "word_prefix", "collector_number", "set_code", "infix"
    ]


class PagedCardSearch(BaseModel):
    items: list[CardSearchResult]
    next_cursor: str | None
    total: int


class CardDetailResponse(BaseModel):
    card_id: str
    name: str
    set_code: str
    set_name: str
    collector_number: str
    card_type: str
    element: str | None
    rune_type: str | None
    subtype: str | None
    attack: int | None
    defence: int | None
    spirit_cost: dict[str, int] | None
    rules_text: str | None
    flavour_text: str | None
    artist: str | None
    #: Every printing, never a filtered subset.
    printings: list[PrintingView]


class SetSummary(BaseModel):
    """User-agnostic by construction — there is deliberately no completion field.

    `/sets` is public and cacheable, and `api-conventions.md` requires public reads never to
    vary on the caller. Completion is per-user, so it is fetched separately and merged in the
    client; putting it here would make a shared cache serve one collector's data to another.
    """
    code: str
    name: str
    series: str | None
    released_on: date | None
    #: The declared printed size — the completion denominator.
    card_count: int
    #: How many we have actually imported. Below `card_count` means an incomplete catalog.
    imported_count: int
    logo_asset_url: str | None


class SetListResponse(BaseModel):
    items: list[SetSummary]


class SetChecklistEntry(BaseModel):
    card_id: str
    collector_number: str
    name: str
    element: str | None
    card_type: str
    printings: list[PrintingView]


class SetChecklistResponse(BaseModel):
    set: SetSummary
    items: list[SetChecklistEntry]
    next_cursor: str | None
    total: int


class StalenessModel(BaseModel):
    last_success_at: datetime | None
    age_hours: float | None
    #: `never_run` is a first-class state, not a null to be interpreted at the call site.
    state: Literal["fresh", "ageing", "stale", "never_run"]


class SourceHealth(BaseModel):
    source: str
    display_name: str
    requires_network: bool
    last_run_id: str | None
    last_status: str | None
    last_started_at: datetime | None
    staleness: StalenessModel


class RejectionRollupModel(BaseModel):
    reason_code: str
    count: int
    example_source_ref: str


class SetCoverageModel(BaseModel):
    set_code: str
    expected: int
    imported: int
    missing_count: int


# --- Inventory (bolt 004, stories 013-015, 023) --------------------------------------

CONDITION = Literal[
    "mint", "near_mint", "lightly_played", "moderately_played", "heavily_played", "damaged",
]


class InventoryItemResponse(BaseModel):
    id: str
    printing_id: str
    condition: CONDITION
    quantity: int
    is_graded: bool
    grader: str | None
    grade: float | None
    acquired_on: date | None
    acquired_unit_price_cents: int | None
    acquired_currency: str | None
    storage_location: str | None
    notes: str | None
    is_for_trade: bool
    created_at: datetime
    updated_at: datetime


class AddInventoryRequest(BaseModel):
    printing_id: str
    condition: CONDITION = "near_mint"
    quantity: int = Field(default=1, ge=1, le=10_000)
    is_graded: bool = False
    grader: str | None = Field(default=None, max_length=16)
    grade: float | None = Field(default=None, ge=0, le=10)
    acquired_on: date | None = None
    acquired_unit_price_cents: int | None = Field(default=None, ge=0)
    acquired_currency: str | None = Field(default=None, min_length=3, max_length=3)
    storage_location: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=512)
    is_for_trade: bool = False


class AddInventoryResponse(BaseModel):
    item: InventoryItemResponse
    #: True when the add folded into an existing row rather than creating one. The fast-add
    #: flow shows this so a collector sees "now 3" instead of wondering where the row went.
    merged: bool


class PatchInventoryRequest(BaseModel):
    condition: CONDITION | None = None
    quantity: int | None = Field(default=None, ge=1, le=10_000)
    is_graded: bool | None = None
    grader: str | None = Field(default=None, max_length=16)
    grade: float | None = Field(default=None, ge=0, le=10)
    acquired_on: date | None = None
    acquired_unit_price_cents: int | None = Field(default=None, ge=0)
    acquired_currency: str | None = Field(default=None, min_length=3, max_length=3)
    storage_location: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=512)
    is_for_trade: bool | None = None


class PagedInventory(BaseModel):
    items: list[InventoryItemResponse]
    next_cursor: str | None
    total: int


class SetCompletionModel(BaseModel):
    set_code: str
    set_name: str
    #: Distinct cards owned, over the declared printed size.
    owned_cards: int
    card_count: int
    #: Total copies held — "142 copies across 98 cards".
    total_quantity: int
    ratio: float


class CompletionResponse(BaseModel):
    sets: list[SetCompletionModel]
    total_items: int
    total_quantity: int


class CatalogHealth(BaseModel):
    sources: list[SourceHealth]
    #: Sets whose imported count is short of the declared printed size.
    sets_below_coverage: list[SetCoverageModel]
    latest_run_id: str | None
    rejections: list[RejectionRollupModel]
