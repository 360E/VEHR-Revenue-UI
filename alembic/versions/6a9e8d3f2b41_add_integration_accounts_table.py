"""add integration accounts table

Revision ID: 6a9e8d3f2b41
Revises: 2d6e4aa1c5f7
Create Date: 2026-02-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6a9e8d3f2b41"
down_revision = "2d6e4aa1c5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_tenant_id", sa.String(length=255), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("refresh_token_enc", sa.Text(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "provider",
            "external_tenant_id",
            "external_user_id",
            name="uq_integration_accounts_org_provider_tenant_user",
        ),
    )
    op.create_index(
        "ix_integration_accounts_organization_id",
        "integration_accounts",
        ["organization_id"],
    )
    op.create_index(
        "ix_integration_accounts_user_id",
        "integration_accounts",
        ["user_id"],
    )
    op.create_index(
        "ix_integration_accounts_provider",
        "integration_accounts",
        ["provider"],
    )


def downgrade() -> None:
    op.drop_index("ix_integration_accounts_provider", table_name="integration_accounts")
    op.drop_index("ix_integration_accounts_user_id", table_name="integration_accounts")
    op.drop_index("ix_integration_accounts_organization_id", table_name="integration_accounts")
    op.drop_table("integration_accounts")
