"""alerts: price_alerts

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-17

Lives in `elestrals`, not the harvester's schema, and that is FR-13 rather than convenience: an
alert is a *user's* row, and `harvest-api` holds no grant on user data. The harvester publishes
`price_daily`; this service reads it, decides, and delivers through the phase-1 outbox.

`direction` is part of the unique key because "tell me when it goes below €20" and "tell me when it
goes above €20" are two different alerts about one card, and both are reasonable to want.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_sub", sa.String(36), nullable=False),
        sa.Column("printing_id", sa.String(36),
                  sa.ForeignKey("printings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False, server_default="below"),
        sa.Column("threshold_cents", sa.BigInteger(), nullable=False),
        # Money always travels with its currency — standards §3.
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_fired_at", sa.DateTime(timezone=True)),
        # A price oscillating around a threshold fires once, not every evaluation.
        sa.Column("cooldown_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_sub", "printing_id", "direction",
                            name="uq_price_alert_user_printing_direction"),
        sa.CheckConstraint("threshold_cents > 0", name="ck_price_alert_threshold_positive"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_price_alerts_active", "price_alerts", ["is_active", "printing_id"])
    op.create_index("ix_price_alerts_user", "price_alerts", ["user_sub"])


def downgrade() -> None:
    op.drop_index("ix_price_alerts_user", table_name="price_alerts")
    op.drop_index("ix_price_alerts_active", table_name="price_alerts")
    op.drop_table("price_alerts")
