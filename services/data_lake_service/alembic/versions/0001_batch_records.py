"""Esquema inicial: tabla batch_records (append-only, ALCOA+).

Revision ID: 0001
Revises:
Create Date: 2026-07-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "batch_records",
        sa.Column("batch_id", sa.String(64), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("reaction_id", sa.String(64), nullable=False, index=True),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("product_nuclide", sa.String(16), nullable=False),
        sa.Column("beam_energy_mev", sa.Float(), nullable=False),
        sa.Column("current_ua", sa.Float(), nullable=False),
        sa.Column("irradiation_time_min", sa.Float(), nullable=False),
        sa.Column("enrichment", sa.Float(), nullable=True),
        sa.Column("saturation_yield_mbq_ua", sa.Float(), nullable=False),
        sa.Column("eob_activity_gbq", sa.Float(), nullable=False),
        sa.Column("eob_activity_gbq_uncertainty", sa.Float(), nullable=False),
        sa.Column("saturation_factor", sa.Float(), nullable=False),
        sa.Column("relative_uncertainty", sa.Float(), nullable=False),
        sa.Column("dataset_id", sa.String(120), nullable=False),
        sa.Column("dataset_sha256", sa.String(64), nullable=True),
        sa.Column("stopping_source", sa.String(120), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("artifact_key", sa.String(256), nullable=True),
        sa.Column("record_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_batch_records_reaction_id",
                    "batch_records", ["reaction_id"])


def downgrade() -> None:
    op.drop_index("ix_batch_records_reaction_id", table_name="batch_records")
    op.drop_table("batch_records")
