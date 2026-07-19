"""0004: tabla audit_events (eventos de proceso declarados: desviaciones).

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("batch_id", sa.String(64), nullable=False, index=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_audit_events_batch_id", "audit_events", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_batch_id", table_name="audit_events")
    op.drop_table("audit_events")
