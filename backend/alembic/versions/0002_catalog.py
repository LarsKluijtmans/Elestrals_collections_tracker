"""catalog: sets, cards, printings, sealed_products, catalog_imports, import_rejections

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-10

The catalog is three levels — sets < cards < printings — and `printings` is the SKU that
inventory, prices and listings all point at. See `standards/data-model.md`.

Two additions relative to that document, both from `ddd-02-technical-design.md`:

  * `content_fingerprint` on `cards` and `printings`, which is what makes "second run:
    0 added, 0 updated" achievable rather than aspirational;
  * `cards_unchanged` on `catalog_imports`, because "unchanged" is the reported success
    signal of a re-run, not the absence of a number.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("series", sa.String(64)),
        sa.Column("released_on", sa.Date()),
        # The PRINTED set size — the completion denominator, declared not counted.
        sa.Column("card_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("logo_asset_url", sa.String(512)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_sets_series", "sets", ["series"])

    op.create_table(
        "cards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("set_id", sa.String(36), sa.ForeignKey("sets.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("collector_number", sa.String(16), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("card_type", sa.String(16), nullable=False),
        sa.Column("element", sa.String(16)),
        sa.Column("rune_type", sa.String(16)),
        sa.Column("subtype", sa.String(64)),
        sa.Column("attack", sa.Integer()),
        sa.Column("defence", sa.Integer()),
        sa.Column("spirit_cost", sa.JSON()),
        sa.Column("rules_text", sa.Text()),
        sa.Column("flavour_text", sa.Text()),
        sa.Column("artist", sa.String(128)),
        sa.Column("content_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("set_id", "collector_number", name="uq_cards_set_number"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_cards_name", "cards", ["name"])
    op.create_index("ix_cards_type_element", "cards", ["card_type", "element"])

    op.create_table(
        "printings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("card_id", sa.String(36), sa.ForeignKey("cards.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("rarity", sa.String(16), nullable=False),
        sa.Column("finish", sa.String(16), nullable=False),
        sa.Column("language", sa.String(5), nullable=False, server_default="en"),
        sa.Column("edition", sa.String(16), nullable=False, server_default="unlimited"),
        sa.Column("image_url", sa.String(512)),
        sa.Column("is_tracked_for_price", sa.Boolean(), nullable=False,
                  server_default=sa.text("1")),
        sa.Column("content_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # The natural key. This is what makes the upsert idempotent under concurrency, not
        # merely in sequence.
        sa.UniqueConstraint("card_id", "rarity", "finish", "language", "edition",
                            name="uq_printings_natural_key"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_printings_card", "printings", ["card_id"])
    op.create_index("ix_printings_tracked", "printings", ["is_tracked_for_price"])

    op.create_table(
        "sealed_products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("set_id", sa.String(36), sa.ForeignKey("sets.id", ondelete="SET NULL")),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("contents_note", sa.String(255)),
        sa.Column("image_url", sa.String(512)),
        sa.Column("is_tracked_for_price", sa.Boolean(), nullable=False,
                  server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_sealed_products_set", "sealed_products", ["set_id"])

    op.create_table(
        "catalog_imports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(48), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("set_codes", sa.JSON()),
        sa.Column("sets_seen", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cards_added", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cards_updated", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cards_unchanged", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("printings_added", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rejected", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_summary", sa.Text()),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_catalog_imports_status_started", "catalog_imports",
                    ["status", "started_at"])
    op.create_index("ix_catalog_imports_source_started", "catalog_imports",
                    ["source", "started_at"])

    op.create_table(
        "import_rejections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("import_id", sa.String(36),
                  sa.ForeignKey("catalog_imports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_ref", sa.String(255), nullable=False),
        sa.Column("raw_record", sa.JSON()),
        sa.Column("reason_code", sa.String(48), nullable=False),
        sa.Column("field", sa.String(64)),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_import_rejections_import_reason", "import_rejections",
                    ["import_id", "reason_code"])


def downgrade() -> None:
    op.drop_index("ix_import_rejections_import_reason", table_name="import_rejections")
    op.drop_table("import_rejections")
    op.drop_index("ix_catalog_imports_source_started", table_name="catalog_imports")
    op.drop_index("ix_catalog_imports_status_started", table_name="catalog_imports")
    op.drop_table("catalog_imports")
    op.drop_index("ix_sealed_products_set", table_name="sealed_products")
    op.drop_table("sealed_products")
    op.drop_index("ix_printings_tracked", table_name="printings")
    op.drop_index("ix_printings_card", table_name="printings")
    op.drop_table("printings")
    op.drop_index("ix_cards_type_element", table_name="cards")
    op.drop_index("ix_cards_name", table_name="cards")
    op.drop_table("cards")
    op.drop_index("ix_sets_series", table_name="sets")
    op.drop_table("sets")
