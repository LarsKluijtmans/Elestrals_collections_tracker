"""profile and sharing: notifications, the outbox, and deletion

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-17

Three concerns, one migration.

`notification_outbox` is the one phase 2 has been waiting on — story 034 (price alerts) was recorded
`blocked` on it, because "an outage delays rather than loses" is an acceptance criterion there and
there was nothing to delay *in*.

The deletion tables are split deliberately: `deletion_requests` holds personal data and goes when the
deletion runs, `deletion_audits` outlives it and holds a **hash** of the subject rather than the
subject. An operator can prove an erasure happened without being able to read who it was about.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_sub", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        # Defaults are conservative: nothing but account-critical mail until asked for.
        sa.Column("channel", sa.String(16), nullable=False, server_default="none"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_notification_pref_user_event", "notification_preferences",
        ["user_sub", "event_type"], unique=True,
    )

    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_sub", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        # Backoff, so one failing recipient does not monopolise every drain cycle.
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(500)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_outbox_status_due", "notification_outbox", ["status", "next_attempt_at"])
    op.create_index("ix_outbox_user", "notification_outbox", ["user_sub"])

    op.create_table(
        "deletion_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_sub", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        # Cancellable until this passes. "I changed my mind" is a thing people say.
        sa.Column("execute_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_deletion_requests_user", "deletion_requests", ["user_sub", "status"])
    op.create_index("ix_deletion_requests_due", "deletion_requests", ["status", "execute_after"])

    op.create_table(
        "deletion_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        # A HASH, never the subject. This row outlives the deletion, so storing the `sub` would
        # mean the erasure did not erase.
        sa.Column("subject_hash", sa.String(64), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("inventory_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("other_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_deletion_audits_request", "deletion_audits", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_deletion_audits_request", table_name="deletion_audits")
    op.drop_table("deletion_audits")
    op.drop_index("ix_deletion_requests_due", table_name="deletion_requests")
    op.drop_index("ix_deletion_requests_user", table_name="deletion_requests")
    op.drop_table("deletion_requests")
    op.drop_index("ix_outbox_user", table_name="notification_outbox")
    op.drop_index("ix_outbox_status_due", table_name="notification_outbox")
    op.drop_table("notification_outbox")
    op.drop_index("ix_notification_pref_user_event", table_name="notification_preferences")
    op.drop_table("notification_preferences")
