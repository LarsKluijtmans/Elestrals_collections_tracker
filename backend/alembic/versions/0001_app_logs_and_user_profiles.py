"""app_logs and user_profiles

Revision ID: 0001
Revises:
Create Date: 2026-08-09

The foundation tables. `app_logs` mirrors the platform's `application_logs` shape plus
`user_sub`/`request_id` for joining against our own domain. `user_profiles` holds only what
the platform has no opinion on — no email, no display name, no avatar.
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
        "app_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("category", sa.String(48), nullable=False),
        sa.Column("component", sa.String(64)),
        sa.Column("operation", sa.String(64)),
        sa.Column("message", sa.String(1024), nullable=False),
        sa.Column("user_sub", sa.String(36)),
        sa.Column("request_id", sa.String(36)),
        sa.Column("status_code", sa.Integer()),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("context", sa.JSON()),
        sa.Column("trace", sa.Text()),
        sa.Column("forwarded_to_platform", sa.Boolean(), nullable=False,
                  server_default=sa.text("0")),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_app_logs_at", "app_logs", ["at"])
    op.create_index("ix_app_logs_level_at", "app_logs", ["level", "at"])
    op.create_index("ix_app_logs_category_at", "app_logs", ["category", "at"])
    op.create_index("ix_app_logs_user_at", "app_logs", ["user_sub", "at"])

    op.create_table(
        "user_profiles",
        # The JWT `sub` is the primary key precisely so a row cannot exist for a subject
        # we never validated.
        sa.Column("user_sub", sa.String(36), primary_key=True),
        sa.Column("handle", sa.String(32), unique=True),
        sa.Column("collection_visibility", sa.String(16), nullable=False,
                  server_default="private"),
        sa.Column("default_currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("condition_scale", sa.String(16), nullable=False, server_default="tcg"),
        sa.Column("share_token", sa.String(43), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("user_profiles")
    op.drop_index("ix_app_logs_user_at", table_name="app_logs")
    op.drop_index("ix_app_logs_category_at", table_name="app_logs")
    op.drop_index("ix_app_logs_level_at", table_name="app_logs")
    op.drop_index("ix_app_logs_at", table_name="app_logs")
    op.drop_table("app_logs")
