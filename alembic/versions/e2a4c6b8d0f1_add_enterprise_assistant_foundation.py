"""add enterprise assistant foundation tables

Revision ID: e2a4c6b8d0f1
Revises: c1d2e3f4a5b6
Create Date: 2026-02-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "e2a4c6b8d0f1"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    json_type = postgresql.JSONB(astext_type=sa.Text()) if dialect == "postgresql" else sa.JSON()

    # Existing ai_messages table: add metadata_json for agent/tool/workstation context.
    with op.batch_alter_table("ai_messages") as batch:
        batch.add_column(sa.Column("metadata_json", sa.Text(), nullable=True))

    op.create_table(
        "assistant_memory_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("tags", json_type, nullable=False),
        sa.Column("source", sa.String(length=80), nullable=True),
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
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ux_assistant_memory_items_org_user_key",
        "assistant_memory_items",
        ["organization_id", "user_id", "key"],
        unique=True,
    )
    op.create_index(
        "ix_assistant_memory_items_org_user_updated",
        "assistant_memory_items",
        ["organization_id", "user_id", "updated_at"],
        unique=False,
    )

    op.create_table(
        "assistant_reminders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("thread_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channels", json_type, nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'scheduled'")),
        sa.Column("repeat_mode", sa.String(length=30), nullable=False, server_default=sa.text("'one_shot'")),
        sa.Column("nag_interval_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("msft_task_id", sa.String(length=255), nullable=True),
        sa.Column("msft_event_id", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["thread_id"], ["ai_threads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_assistant_reminders_org_user_status_due",
        "assistant_reminders",
        ["organization_id", "user_id", "status", "due_at"],
        unique=False,
    )
    op.create_index(
        "ix_assistant_reminders_org_user_due",
        "assistant_reminders",
        ["organization_id", "user_id", "due_at"],
        unique=False,
    )

    op.create_table(
        "assistant_notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("reminder_id", sa.String(length=36), nullable=True),
        sa.Column("type", sa.String(length=40), nullable=False, server_default=sa.text("'notification'")),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("channel", sa.String(length=40), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_targets", json_type, nullable=False),
        sa.ForeignKeyConstraint(["reminder_id"], ["assistant_reminders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ux_assistant_notifications_idempotency",
        "assistant_notifications",
        ["reminder_id", "channel", "due_at", "attempt"],
        unique=True,
    )
    op.create_index(
        "ix_assistant_notifications_org_user_delivery",
        "assistant_notifications",
        ["organization_id", "user_id", "delivered_at", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_notifications_org_user_delivery", table_name="assistant_notifications")
    op.drop_index("ux_assistant_notifications_idempotency", table_name="assistant_notifications")
    op.drop_table("assistant_notifications")

    op.drop_index("ix_assistant_reminders_org_user_due", table_name="assistant_reminders")
    op.drop_index("ix_assistant_reminders_org_user_status_due", table_name="assistant_reminders")
    op.drop_table("assistant_reminders")

    op.drop_index("ix_assistant_memory_items_org_user_updated", table_name="assistant_memory_items")
    op.drop_index("ux_assistant_memory_items_org_user_key", table_name="assistant_memory_items")
    op.drop_table("assistant_memory_items")

    with op.batch_alter_table("ai_messages") as batch:
        batch.drop_column("metadata_json")
