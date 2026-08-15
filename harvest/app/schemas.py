"""Response shapes for the admin API.

Explicit models rather than returning ORM rows: the admin console is the one place raw harvest
data is exposed, and "what exactly leaves this service" should be readable in one file. Two
things are absent from every shape here and always will be — buyer and seller identity, because
neither was ever collected.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class SourceHealth(BaseModel):
    key: str
    name: str
    access_mode: str
    enabled: bool
    reports_sold: bool
    rate_limit_per_min: int
    #: Shown next to the name in the console on purpose. ADR-004 accepts a risk per source; the
    #: note and the person who accepted it belong where an admin sees them every time they look
    #: at the pipeline, not filed somewhere they would have to go and find.
    tos_review_note: str | None
    risk_accepted_by: str | None
    risk_accepted_on: date | None

    quarantined: bool
    quarantined_until: datetime | None
    quarantine_reason: str | None
    quarantine_level: int

    last_deep_run: "RunSummary | None" = None
    last_light_run: "RunSummary | None" = None
    #: `(started_at, accept_rate)` per recent run, per mode. Trended rather than shown as a
    #: single latest value: the drop is the signal, not the number.
    accept_rate_deep: list[tuple[datetime, float]] = []
    accept_rate_light: list[tuple[datetime, float]] = []
    live_listings: int = 0
    #: True when this source has never run, which is a different state from "ran and found
    #: nothing" and must not look the same in the console.
    never_run: bool = True


class RunSummary(BaseModel):
    id: str
    source_key: str
    mode: str
    status: str
    triggered_by: str
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float | None
    queries: int
    fetched: int
    parsed: int
    accepted: int
    rejected: int
    discovered: int
    ended: int
    error_summary: str | None
    stop_requested: bool

    @property
    def accept_rate(self) -> float | None:
        return (self.accepted / self.parsed) if self.parsed else None


class PagedRuns(BaseModel):
    items: list[RunSummary]
    total: int


class ListingSummary(BaseModel):
    id: str
    source_key: str
    external_id: str
    title: str
    url: str
    image_url: str | None
    kind: str
    #: The four-value status, and the UI must render `ended_unknown` as "ended, reason unknown".
    #: Describing it as sold would undo the whole invariant chain in one label.
    status: str
    price_cents: int
    currency: str
    shipping_cents: int | None
    quantity: int
    buying_format: str
    location_country: str | None

    printing_id: str | None
    sealed_product_id: str | None
    condition: str | None
    match_confidence: float | None
    #: Why it matched, or why it did not. The most useful column in the explorer.
    match_note: str | None
    #: Resolved from the catalog in a second pass; `None` when the printing no longer exists,
    #: which the UI shows as unmatched rather than pretending.
    product_label: str | None = None

    first_seen_at: datetime
    last_seen_at: datetime
    ended_at: datetime | None
    sold_price_cents: int | None


class PagedListings(BaseModel):
    items: list[ListingSummary]
    total: int


class RejectionReason(BaseModel):
    reason: str
    count: int


class CoveragePoint(BaseModel):
    day: date
    tracked: int
    with_recent_sold: int

    @property
    def ratio(self) -> float:
        return (self.with_recent_sold / self.tracked) if self.tracked else 0.0


class MatchQuality(BaseModel):
    source_key: str
    mode: str
    points: list[tuple[datetime, float]]


class CoverageReport(BaseModel):
    tracked_printings: int
    priced_printings: int
    #: Separated from the above because the Must-level goal is about **owned** printings, and a
    #: high ratio over a small tracked set is not the same achievement.
    window_days: int
    match_quality: list[MatchQuality]
    top_rejections: list[RejectionReason]
    unmatched_no_catalog: int
    unmatched_under_floor: int


class ObservationPoint(BaseModel):
    id: int
    source_key: str
    sale_type: str
    observed_at: datetime
    price_cents: int
    currency: str
    condition: str | None
    #: Drawn distinctly by the UI. Flagged rather than deleted, so the rollup stays auditable.
    is_outlier: bool
    source_url: str


class SourceAgreement(BaseModel):
    source_key: str
    median_cents: int
    observation_count: int
    #: Signed percentage difference from the cross-source median. A source consistently high on
    #: every printing is a broken connector; one scattered around the others is a thin market.
    delta_pct: float


class DistributionReport(BaseModel):
    printing_id: str | None
    sealed_product_id: str | None
    product_label: str | None
    day: date | None
    points: list[ObservationPoint]
    agreement: list[SourceAgreement]
    single_source: bool


class TriggerAccepted(BaseModel):
    run_id: str
    source_key: str
    mode: str
    status: str


SourceHealth.model_rebuild()
