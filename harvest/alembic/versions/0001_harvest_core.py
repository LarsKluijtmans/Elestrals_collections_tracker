"""harvest core: sources, runs, listings, observations, rollups and fx

Revision ID: 0001
Revises:
Create Date: 2026-08-15

The first migration of the second backend, in its **own** tree. It creates
`elestrals_harvest` and nothing else — `elestrals` belongs to `elestrals-api`, and the user this
runs as has no privilege to touch it.

`ck_price_sources_risk_accepted_before_enabled` is the load-bearing constraint. FR-1 under
ADR-004 requires that a source cannot be enabled until someone has written down what its terms
say **and** put their name to accepting the risk. A requirement that lives only in a service
method is one refactor away from being a comment; MySQL has enforced CHECK since 8.0.16 and
SQLite always has, so this holds on both paths.

There is deliberately **no seed here**. Migration 0004 of the old single-backend layout seeded
two disabled sources with their review notes pre-written; that was reasonable when the notes were
"this route is closed". Under ADR-004 the note records an accepted risk with a named person, and
a migration cannot accept a risk on someone's behalf. Use `python -m app.harvest --enable KEY
--note "..." --accepted-by "..."`, which requires both.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("base_url", sa.String(255), nullable=False),
        sa.Column("access_mode", sa.String(16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("tos_review_note", sa.Text()),
        sa.Column("risk_accepted_by", sa.String(128)),
        sa.Column("risk_accepted_on", sa.Date()),
        sa.Column("robots_checked_on", sa.Date()),
        sa.Column("rate_limit_per_min", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("weight", sa.Numeric(3, 2), nullable=False, server_default=sa.text("1.00")),
        sa.Column("reports_sold", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("quarantined_until", sa.DateTime(timezone=True)),
        sa.Column("quarantine_reason", sa.String(255)),
        sa.Column("quarantine_level", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "enabled = 0 OR (tos_review_note IS NOT NULL AND risk_accepted_by IS NOT NULL)",
            name="ck_price_sources_risk_accepted_before_enabled",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    op.create_table(
        "harvest_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36),
                  sa.ForeignKey("price_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("queries", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("fetched", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("parsed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("accepted", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rejected", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("discovered", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("ended", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_summary", sa.Text()),
        sa.Column("triggered_by", sa.String(16), nullable=False, server_default="schedule"),
        sa.Column("stop_requested", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_harvest_runs_source_started", "harvest_runs", ["source_id", "started_at"])
    op.create_index("ix_harvest_runs_status_started", "harvest_runs", ["status", "started_at"])

    op.create_table(
        "market_listings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36),
                  sa.ForeignKey("price_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(320), nullable=False),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("image_url", sa.String(512)),
        sa.Column("kind", sa.String(16), nullable=False, server_default="unknown"),
        # Cross-schema references by id, deliberately NOT foreign keys: they point into
        # `elestrals`, which this service cannot write and does not own. A cross-schema FK would
        # make phase 1 unable to change its own catalog without this service's cooperation.
        sa.Column("printing_id", sa.String(36)),
        sa.Column("sealed_product_id", sa.String(36)),
        sa.Column("condition", sa.String(24)),
        sa.Column("match_confidence", sa.Numeric(3, 2)),
        sa.Column("match_note", sa.String(255)),
        sa.Column("price_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("shipping_cents", sa.BigInteger()),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("buying_format", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("location_country", sa.String(2)),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("sold_price_cents", sa.BigInteger()),
        sa.Column("first_seen_run_id", sa.String(36)),
        sa.Column("last_seen_run_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_id", "external_id", name="uq_market_listings_source_external"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_market_listings_source_status_seen", "market_listings",
                    ["source_id", "status", "last_seen_at"])
    op.create_index("ix_market_listings_printing", "market_listings", ["printing_id", "status"])
    op.create_index("ix_market_listings_sealed", "market_listings",
                    ["sealed_product_id", "status"])
    op.create_index("ix_market_listings_unmatched", "market_listings",
                    ["source_id", "kind", "match_confidence"])
    op.create_index("ix_market_listings_seen", "market_listings", ["last_seen_at"])

    op.create_table(
        "price_observations",
        # BIGINT, not a UUID: 50M rows is the NFR target and a random key of that width is a
        # page-split machine. Legal because this id never appears in a response.
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                  primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(36),
                  sa.ForeignKey("price_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(36),
                  sa.ForeignKey("harvest_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("printing_id", sa.String(36)),
        sa.Column("sealed_product_id", sa.String(36)),
        sa.Column("condition", sa.String(24)),
        sa.Column("sale_type", sa.String(8), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("shipping_cents", sa.BigInteger()),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("source_url", sa.String(512), nullable=False),
        sa.Column("match_confidence", sa.Numeric(3, 2), nullable=False),
        sa.Column("is_outlier", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_excluded", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_id", "external_id",
                            name="uq_price_observations_source_external"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_price_observations_printing_observed", "price_observations",
                    ["printing_id", "observed_at"])
    op.create_index("ix_price_observations_sealed_observed", "price_observations",
                    ["sealed_product_id", "observed_at"])
    op.create_index("ix_price_observations_run", "price_observations", ["run_id"])
    op.create_index("ix_price_observations_day", "price_observations",
                    ["observed_at", "sale_type"])

    op.create_table(
        "price_daily",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("printing_id", sa.String(36)),
        sa.Column("sealed_product_id", sa.String(36)),
        sa.Column("condition", sa.String(24)),
        # Both MySQL and SQLite treat NULLs as distinct in a unique index, so a key built from
        # the three nullable columns above would not constrain the rows where they are null —
        # which is most of them. These carry the same information with no nulls in it, and the
        # unique key is built from them. Same lesson as `uq_inventory_merge` in phase 1.
        sa.Column("product_key", sa.String(36), nullable=False),
        sa.Column("product_kind", sa.String(8), nullable=False),
        sa.Column("condition_key", sa.String(24), nullable=False, server_default=""),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("sale_type", sa.String(8), nullable=False),
        sa.Column("low_cents", sa.BigInteger(), nullable=False),
        sa.Column("median_cents", sa.BigInteger(), nullable=False),
        sa.Column("high_cents", sa.BigInteger(), nullable=False),
        sa.Column("mean_cents", sa.BigInteger(), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("excluded_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("confidence", sa.String(8), nullable=False, server_default="low"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "product_key", "product_kind", "condition_key", "day", "currency", "sale_type",
            name="uq_price_daily_key",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_price_daily_printing_day", "price_daily", ["printing_id", "day"])
    op.create_index("ix_price_daily_sealed_day", "price_daily", ["sealed_product_id", "day"])
    op.create_index("ix_price_daily_day_type", "price_daily", ["day", "sale_type"])

    op.create_table(
        "fx_rates",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("base", sa.String(3), primary_key=True),
        sa.Column("quote", sa.String(3), primary_key=True),
        sa.Column("rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("is_carried_forward", sa.Boolean(), nullable=False,
                  server_default=sa.text("0")),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("fx_rates")
    op.drop_index("ix_price_daily_day_type", table_name="price_daily")
    op.drop_index("ix_price_daily_sealed_day", table_name="price_daily")
    op.drop_index("ix_price_daily_printing_day", table_name="price_daily")
    op.drop_table("price_daily")
    op.drop_index("ix_price_observations_day", table_name="price_observations")
    op.drop_index("ix_price_observations_run", table_name="price_observations")
    op.drop_index("ix_price_observations_sealed_observed", table_name="price_observations")
    op.drop_index("ix_price_observations_printing_observed", table_name="price_observations")
    op.drop_table("price_observations")
    op.drop_index("ix_market_listings_seen", table_name="market_listings")
    op.drop_index("ix_market_listings_unmatched", table_name="market_listings")
    op.drop_index("ix_market_listings_sealed", table_name="market_listings")
    op.drop_index("ix_market_listings_printing", table_name="market_listings")
    op.drop_index("ix_market_listings_source_status_seen", table_name="market_listings")
    op.drop_table("market_listings")
    op.drop_index("ix_harvest_runs_status_started", table_name="harvest_runs")
    op.drop_index("ix_harvest_runs_source_started", table_name="harvest_runs")
    op.drop_table("harvest_runs")
    op.drop_table("price_sources")
