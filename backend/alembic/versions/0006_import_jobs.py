"""import/export: import_jobs and import_rows

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-17

The dry run's state, persisted between mapping and commit. Story 028 requires the job to survive
leaving the page — a 5,000-row dry run is not something to make someone sit through twice — and
server memory is the wrong place to park an untrusted upload while a human decides about it.

Named at a deliberate distance from `catalog_imports`, which records *our catalog* being imported
from a data source. These record *a user's collection* being imported from their spreadsheet. Same
word, nothing else in common, and conflating them would put user-uploaded content in a table the
operator console reads.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_sub", sa.String(36), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="mapping"),
        # Reported back so a mangled preview has a diagnosable cause rather than a vague one.
        sa.Column("encoding", sa.String(16), nullable=False, server_default="utf-8"),
        sa.Column("delimiter", sa.String(4), nullable=False, server_default=","),
        sa.Column("mapping", sa.JSON(), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("add_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("update_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("needs_confirmation_count", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_import_jobs_user", "import_jobs", ["user_sub", "created_at"])

    op.create_table(
        "import_rows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36),
                  sa.ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False),
        # 1-based, as a spreadsheet numbers them: "row 900" must mean the row the user can see.
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("raw", sa.JSON(), nullable=False),
        sa.Column("verdict", sa.String(24), nullable=False, server_default="rejected"),
        sa.Column("match_rung", sa.String(24), nullable=False, server_default="none"),
        sa.Column("match_score", sa.Float()),
        sa.Column("printing_id", sa.String(36)),
        sa.Column("quantity", sa.Integer()),
        sa.Column("condition", sa.String(24)),
        sa.Column("reason", sa.String(255)),
        # Only ever true because a human said so, and only relevant to fuzzy matches.
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_import_rows_job", "import_rows", ["job_id", "line_number"])


def downgrade() -> None:
    op.drop_index("ix_import_rows_job", table_name="import_rows")
    op.drop_table("import_rows")
    op.drop_index("ix_import_jobs_user", table_name="import_jobs")
    op.drop_table("import_jobs")
