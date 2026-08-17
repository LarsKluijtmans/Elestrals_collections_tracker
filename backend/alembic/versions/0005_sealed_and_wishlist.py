"""sealed and wishlist: sealed_inventory_items and wishlist_items

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-17

Two tables, and one decision in each worth reading.

**Sealed inventory is its own table, not a `kind` column on `inventory_items`.** Story 025 requires
sealed holdings to appear in neither the collection table nor any completion figure, and the only
way to guarantee that permanently is for them not to live where those queries look. A shared table
would put the burden on every future query remembering to exclude sealed — and the one that forgets
counts a booster box as a card.

**`wishlist_items` refuses half a price.** `max_price_cents` and `max_price_currency` are both-or-
neither at the schema level, because "500" without a currency is not money and a half-set price
looks like a real one.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sealed_inventory_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_sub", sa.String(36), nullable=False),
        sa.Column("sealed_product_id", sa.String(36),
                  sa.ForeignKey("sealed_products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
        # One-way. A box that has been opened cannot be re-sealed, and the model does not offer it.
        sa.Column("is_sealed", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("acquired_on", sa.Date()),
        sa.Column("acquired_unit_price_cents", sa.BigInteger()),
        sa.Column("acquired_currency", sa.String(3)),
        sa.Column("storage_location", sa.String(64)),
        sa.Column("notes", sa.String(512)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # `is_sealed` is part of the key, so a sealed box and an opened one stay separate rows.
        sa.UniqueConstraint("user_sub", "sealed_product_id", "is_sealed",
                            name="uq_sealed_inventory_merge"),
        sa.CheckConstraint("quantity > 0", name="ck_sealed_quantity_positive"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_sealed_inventory_user", "sealed_inventory_items", ["user_sub"])

    op.create_table(
        "wishlist_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_sub", sa.String(36), nullable=False),
        sa.Column("printing_id", sa.String(36),
                  sa.ForeignKey("printings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("desired_quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("priority", sa.String(8), nullable=False, server_default="normal"),
        sa.Column("max_price_cents", sa.BigInteger()),
        sa.Column("max_price_currency", sa.String(3)),
        sa.Column("notes", sa.String(512)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_sub", "printing_id", name="uq_wishlist_user_printing"),
        sa.CheckConstraint("desired_quantity > 0", name="ck_wishlist_quantity_positive"),
        # Both or neither. A bare number is not money.
        sa.CheckConstraint(
            "(max_price_cents IS NULL AND max_price_currency IS NULL) "
            "OR (max_price_cents IS NOT NULL AND max_price_currency IS NOT NULL)",
            name="ck_wishlist_price_is_money",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_wishlist_user", "wishlist_items", ["user_sub"])


def downgrade() -> None:
    op.drop_index("ix_wishlist_user", table_name="wishlist_items")
    op.drop_table("wishlist_items")
    op.drop_index("ix_sealed_inventory_user", table_name="sealed_inventory_items")
    op.drop_table("sealed_inventory_items")
