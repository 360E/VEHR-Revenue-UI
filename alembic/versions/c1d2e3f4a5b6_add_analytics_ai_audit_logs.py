"""add analytics ai audit logs

Revision ID: c1d2e3f4a5b6
Revises: f6a1c2d3e4b5
Create Date: 2026-02-15 00:00:05.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c1d2e3f4a5b6"
down_revision = "f6a1c2d3e4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    uuid_type = postgresql.UUID(as_uuid=False) if dialect == "postgresql" else sa.String(length=36)
    json_type = postgresql.JSONB(astext_type=sa.Text()) if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "analytics_ai_audit_logs",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organization_id", uuid_type, nullable=False),
        sa.Column("membership_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("report_key", sa.String(length=120), nullable=True),
        sa.Column("conversation_id", uuid_type, nullable=False),
        sa.Column("message_id", uuid_type, nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(length=80), nullable=False, server_default=sa.text("'dashboard_question'")),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("metrics_used", json_type, nullable=False),
        sa.Column("filters_applied", json_type, nullable=False),
        sa.Column("query_requests", json_type, nullable=False),
        sa.Column("query_responses_summary", json_type, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_analytics_ai_audit_logs_org_created",
        "analytics_ai_audit_logs",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_analytics_ai_audit_logs_org_report_created",
        "analytics_ai_audit_logs",
        ["organization_id", "report_key", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_analytics_ai_audit_logs_org_conversation_created",
        "analytics_ai_audit_logs",
        ["organization_id", "conversation_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_analytics_ai_audit_logs_org_conversation_created", table_name="analytics_ai_audit_logs")
    op.drop_index("ix_analytics_ai_audit_logs_org_report_created", table_name="analytics_ai_audit_logs")
    op.drop_index("ix_analytics_ai_audit_logs_org_created", table_name="analytics_ai_audit_logs")
    op.drop_table("analytics_ai_audit_logs")

