"""add file sha256 for era duplicate detection

Revision ID: a1b2c3d4e5f7
Revises: 5a8c1d2e3f4b
Create Date: 2026-02-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "5a8c1d2e3f4b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "revenue_era_files",
        sa.Column("file_sha256", sa.String(length=64), nullable=True),
    )
    op.execute(sa.text("UPDATE revenue_era_files SET file_sha256 = sha256 WHERE file_sha256 IS NULL"))
    op.alter_column("revenue_era_files", "file_sha256", nullable=False)
    op.create_unique_constraint(
        "uq_revenue_era_files_org_file_sha256",
        "revenue_era_files",
        ["organization_id", "file_sha256"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_revenue_era_files_org_file_sha256", "revenue_era_files", type_="unique")
    op.drop_column("revenue_era_files", "file_sha256")
