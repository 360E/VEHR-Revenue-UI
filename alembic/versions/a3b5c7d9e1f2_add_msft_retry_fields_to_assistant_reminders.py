"""add msft retry fields to assistant reminders

Revision ID: a3b5c7d9e1f2
Revises: f7c3a9b1d2e4
Create Date: 2026-02-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "a3b5c7d9e1f2"
down_revision = "f7c3a9b1d2e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    json_type = postgresql.JSONB(astext_type=sa.Text()) if dialect == "postgresql" else sa.JSON()
    empty_json_default = sa.text("'{}'::jsonb") if dialect == "postgresql" else sa.text("'{}'")

    with op.batch_alter_table("assistant_reminders") as batch:
        batch.add_column(
            sa.Column(
                "msft_channel_status_json",
                json_type,
                nullable=False,
                server_default=empty_json_default,
            )
        )
        batch.add_column(sa.Column("msft_last_error", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column(
                "msft_attempt_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch.add_column(sa.Column("msft_next_attempt_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index(
        "ix_assistant_reminders_msft_next_attempt_at",
        "assistant_reminders",
        ["msft_next_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_reminders_msft_next_attempt_at", table_name="assistant_reminders")

    with op.batch_alter_table("assistant_reminders") as batch:
        batch.drop_column("msft_next_attempt_at")
        batch.drop_column("msft_attempt_count")
        batch.drop_column("msft_last_error")
        batch.drop_column("msft_channel_status_json")

