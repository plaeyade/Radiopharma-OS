"""0003: tabla ebr_signatures (firmas electrónicas 21 CFR Part 11).

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ebr_signatures",
        sa.Column("signature_id", sa.String(64), primary_key=True),
        sa.Column("batch_id", sa.String(64), nullable=False, index=True),
        sa.Column("signed_by", sa.String(120), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meaning", sa.String(32), nullable=False),
        sa.Column("record_hash_signed", sa.String(64), nullable=False),
        sa.Column("signature_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_ebr_signatures_batch_id", "ebr_signatures", ["batch_id"])
    # Sello de tiempo de la decisión de liberación (pista de auditoría eBR)
    op.add_column("batch_records",
                  sa.Column("released_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("batch_records", "released_at")
    op.drop_index("ix_ebr_signatures_batch_id", table_name="ebr_signatures")
    op.drop_table("ebr_signatures")
