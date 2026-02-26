"""add revenue external claim links

Revision ID: f1e2d3c4b5a8
Revises: ab4d6e8f1c2a
Create Date: 2026-02-21 18:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1e2d3c4b5a8"
down_revision = "ab4d6e8f1c2a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revenue_external_claim_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("external_system", sa.String(length=100), nullable=False),
        sa.Column("external_claim_id", sa.String(length=255), nullable=False),
        sa.Column("era_file_id", sa.String(length=36), nullable=True),
        sa.Column("claim_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["era_file_id"], ["revenue_era_files.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "external_system",
            "external_claim_id",
            name="uq_revenue_external_claim_links_org_system_claim",
        ),
    )
    op.create_index(
        op.f("ix_revenue_external_claim_links_organization_id"),
        "revenue_external_claim_links",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_revenue_external_claim_links_organization_id"), table_name="revenue_external_claim_links")
    op.drop_table("revenue_external_claim_links")
