"""add revenue era processing logs

Revision ID: 0f7e3d2c1b45
Revises: 4e2f1c3a5b6d
Create Date: 2026-02-19 19:50:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0f7e3d2c1b45"
down_revision = "4e2f1c3a5b6d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revenue_era_processing_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("era_file_id", sa.String(length=36), nullable=False),
        sa.Column("stage", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["era_file_id"], ["revenue_era_files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_revenue_era_processing_logs_file",
        "revenue_era_processing_logs",
        ["era_file_id"],
        unique=False,
    )
    op.create_index(
        "ix_revenue_era_processing_logs_stage",
        "revenue_era_processing_logs",
        ["stage"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_revenue_era_processing_logs_stage", table_name="revenue_era_processing_logs")
    op.drop_index("ix_revenue_era_processing_logs_file", table_name="revenue_era_processing_logs")
    op.drop_table("revenue_era_processing_logs")
