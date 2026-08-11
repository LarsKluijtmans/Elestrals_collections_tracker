"""inventory: inventory_items and the set_completion projection

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-11

`uq_inventory_merge` over `(user_sub, printing_id, merge_condition)` is the load-bearing
constraint of the whole bolt. `merge_condition` holds the condition for ungraded rows and NULL
for graded ones, and because both MySQL and SQLite treat NULLs as distinct in a unique index,
graded copies never collide while ungraded ones merge. That is what lets the add path be a
single atomic upsert instead of a read-then-write that loses rows under the concurrent requests
the fast-add flow generates by design.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.String(36), primary_key=True),
        # Every index leads with this. Ownership is not a filter someone remembers to add.
        sa.Column("user_sub", sa.String(36), nullable=False),
        sa.Column("printing_id", sa.String(36),
                  sa.ForeignKey("printings.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("condition", sa.String(24), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_graded", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("grader", sa.String(16)),
        sa.Column("grade", sa.Numeric(3, 1)),
        # condition when ungraded, NULL when graded — the merge discriminator.
        sa.Column("merge_condition", sa.String(24)),
        sa.Column("acquired_on", sa.Date()),
        sa.Column("acquired_unit_price_cents", sa.BigInteger()),
        sa.Column("acquired_currency", sa.String(3)),
        sa.Column("storage_location", sa.String(64)),
        sa.Column("notes", sa.String(512)),
        sa.Column("is_for_trade", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_sub", "printing_id", "merge_condition",
                            name="uq_inventory_merge"),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_quantity_positive"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_inventory_user_printing", "inventory_items", ["user_sub", "printing_id"])
    op.create_index("ix_inventory_user_created", "inventory_items", ["user_sub", "created_at"])

    op.create_table(
        "set_completion",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_sub", sa.String(36), nullable=False),
        sa.Column("set_id", sa.String(36), sa.ForeignKey("sets.id", ondelete="CASCADE"),
                  nullable=False),
        # Distinct cards owned, over the set's declared printed size. Cards, not printings:
        # 126 cards can carry 189 printings and the wrong denominator reads above 100%.
        sa.Column("owned_cards", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("card_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_sub", "set_id", name="uq_set_completion_user_set"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_set_completion_user", "set_completion", ["user_sub"])


def downgrade() -> None:
    op.drop_index("ix_set_completion_user", table_name="set_completion")
    op.drop_table("set_completion")
    op.drop_index("ix_inventory_user_created", table_name="inventory_items")
    op.drop_index("ix_inventory_user_printing", table_name="inventory_items")
    op.drop_table("inventory_items")
