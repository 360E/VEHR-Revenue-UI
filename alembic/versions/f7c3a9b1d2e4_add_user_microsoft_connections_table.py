"""add user microsoft connections table

Revision ID: f7c3a9b1d2e4
Revises: e2a4c6b8d0f1
Create Date: 2026-02-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "f7c3a9b1d2e4"
down_revision = "e2a4c6b8d0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    json_type = postgresql.JSONB(astext_type=sa.Text()) if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "user_microsoft_connections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("msft_user_id", sa.Text(), nullable=True),
        sa.Column("scopes", json_type, nullable=False),
        sa.Column("token_cache_encrypted", sa.Text(), nullable=False),
        sa.Column("todo_list_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_user_microsoft_connections_org_user",
        ),
    )

    op.create_index(
        "ix_user_microsoft_connections_organization_id",
        "user_microsoft_connections",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_microsoft_connections_user_id",
        "user_microsoft_connections",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_microsoft_connections_user_id", table_name="user_microsoft_connections")
    op.drop_index("ix_user_microsoft_connections_organization_id", table_name="user_microsoft_connections")
    op.drop_table("user_microsoft_connections")

