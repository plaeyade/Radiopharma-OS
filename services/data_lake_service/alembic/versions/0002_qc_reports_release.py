"""0002: tabla qc_reports + columnas de liberación en batch_records.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qc_reports",
        sa.Column("qc_id", sa.String(64), primary_key=True),
        sa.Column("batch_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("product", sa.String(64), nullable=False),
        sa.Column("nuclide", sa.String(16), nullable=False),
        sa.Column("overall_status", sa.String(16), nullable=False),
        sa.Column("rules_json", sa.Text(), nullable=False),
        sa.Column("half_life_fit_json", sa.Text(), nullable=True),
        sa.Column("record_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_qc_reports_batch_id", "qc_reports", ["batch_id"])
    op.add_column("batch_records",
                  sa.Column("release_status", sa.String(16),
                            nullable=False, server_default="pending"))
    op.add_column("batch_records",
                  sa.Column("released_by", sa.String(120), nullable=True))
    op.add_column("batch_records",
                  sa.Column("release_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("batch_records", "release_reason")
    op.drop_column("batch_records", "released_by")
    op.drop_column("batch_records", "release_status")
    op.drop_index("ix_qc_reports_batch_id", table_name="qc_reports")
    op.drop_table("qc_reports")
