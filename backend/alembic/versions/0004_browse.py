"""browse: collection_snapshots and saved_views

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-17

Two tables that look unrelated and are, except that bolt 006 is where both became due.

`collection_snapshots` is the one worth reading about. It is written by phase 1 and read by phase 2,
and its whole value is being *old* — the portfolio chart is not empty on launch day because the
history already exists. `total_value_cents` is nullable because phase 1 has no prices: NULL means
"not valued", 0 would mean "worth nothing", and only one of those is true. Phase 2's nightly
valuation updates these same rows in place, which is what `uq_collection_snapshot_user_day` makes
safe.

`saved_views` stores the filter set as JSON in exactly the shape story 020 serialises into the URL.
One encoding, so a saved view and a shared link cannot drift apart.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collection_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_sub", sa.String(36), nullable=False),
        # The day described, not the day written — so a back-fill lands on the right day.
        sa.Column("taken_on", sa.Date(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("distinct_printings", sa.Integer(), nullable=False, server_default=sa.text("0")),
        # Nullable on purpose. Phase 1 counts; phase 2 values. A zero here would be a false claim.
        sa.Column("total_value_cents", sa.BigInteger()),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("valuation_confidence", sa.String(8), nullable=False, server_default="none"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Makes the nightly job idempotent and lets phase 2 update a day rather than append one.
        sa.UniqueConstraint("user_sub", "taken_on", name="uq_collection_snapshot_user_day"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_collection_snapshot_user_day", "collection_snapshots", ["user_sub", "taken_on"]
    )

    op.create_table(
        "saved_views",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_sub", sa.String(36), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("sort", sa.String(32), nullable=False, server_default="added_desc"),
        sa.Column("density", sa.String(16), nullable=False, server_default="comfortable"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_sub", "name", name="uq_saved_view_user_name"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_saved_view_user", "saved_views", ["user_sub"])

    # The keyset cursor for the collection table sorts on `(created_at DESC, id ASC)`, and the
    # existing `ix_inventory_user_created` stops at `created_at` — so the tie-break falls back to a
    # filesort exactly where the 10,000-row target lives. Two columns is the difference between a
    # covering seek and a sort.
    op.create_index(
        "ix_inventory_user_created_id", "inventory_items", ["user_sub", "created_at", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_user_created_id", table_name="inventory_items")
    op.drop_index("ix_saved_view_user", table_name="saved_views")
    op.drop_table("saved_views")
    op.drop_index("ix_collection_snapshot_user_day", table_name="collection_snapshots")
    op.drop_table("collection_snapshots")
