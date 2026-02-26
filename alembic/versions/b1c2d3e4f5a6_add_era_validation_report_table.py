"""add era validation report table

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f7
Create Date: 2026-02-21 00:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a6"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "era_validation_report",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("era_file_id", sa.String(length=36), nullable=False),
        sa.Column("claim_count", sa.Integer(), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False),
        sa.Column("work_item_count", sa.Integer(), nullable=False),
        sa.Column("total_paid_cents", sa.BigInteger(), nullable=False),
        sa.Column("total_adjustment_cents", sa.BigInteger(), nullable=False),
        sa.Column("total_patient_resp_cents", sa.BigInteger(), nullable=False),
        sa.Column("net_cents", sa.BigInteger(), nullable=False),
        sa.Column("reconciled", sa.Boolean(), nullable=False),
        sa.Column("declared_total_missing", sa.Boolean(), nullable=False),
        sa.Column("phi_scan_passed", sa.Boolean(), nullable=False),
        sa.Column("phi_hit_count", sa.Integer(), nullable=False),
        sa.Column("finalized", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["era_file_id"], ["revenue_era_files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_era_validation_report_org_id", "era_validation_report", ["org_id"], unique=False)
    op.create_index("ix_era_validation_report_era_file_id", "era_validation_report", ["era_file_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_era_validation_report_era_file_id", table_name="era_validation_report")
    op.drop_index("ix_era_validation_report_org_id", table_name="era_validation_report")
    op.drop_table("era_validation_report")
