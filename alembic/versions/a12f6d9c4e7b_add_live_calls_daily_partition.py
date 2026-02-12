"""add live_calls table with call_date partitioning

Revision ID: a12f6d9c4e7b
Revises: f2b3c4d5e6f7
Create Date: 2026-02-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a12f6d9c4e7b"
down_revision = "f2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "live_calls",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("rc_call_id", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=40), nullable=False, server_default="unknown"),
        sa.Column("disposition", sa.String(length=64), nullable=True),
        sa.Column("from_number", sa.String(length=64), nullable=True),
        sa.Column("to_number", sa.String(length=64), nullable=True),
        sa.Column("direction", sa.String(length=64), nullable=True),
        sa.Column("extension_id", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("last_event_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("missed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("call_date", sa.Date(), nullable=False),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "session_id", name="uq_live_calls_org_session_id"),
    )
    op.create_index("ix_live_calls_organization_id", "live_calls", ["organization_id"])
    op.create_index("ix_live_calls_session_id", "live_calls", ["session_id"])
    op.create_index("ix_live_calls_rc_call_id", "live_calls", ["rc_call_id"])
    op.create_index("ix_live_calls_state", "live_calls", ["state"])
    op.create_index("ix_live_calls_extension_id", "live_calls", ["extension_id"])
    op.create_index("ix_live_calls_last_event_at", "live_calls", ["last_event_at"])
    op.create_index("ix_live_calls_missed", "live_calls", ["missed"])
    op.create_index("ix_live_calls_call_date", "live_calls", ["call_date"])


def downgrade() -> None:
    op.drop_index("ix_live_calls_call_date", table_name="live_calls")
    op.drop_index("ix_live_calls_missed", table_name="live_calls")
    op.drop_index("ix_live_calls_last_event_at", table_name="live_calls")
    op.drop_index("ix_live_calls_extension_id", table_name="live_calls")
    op.drop_index("ix_live_calls_state", table_name="live_calls")
    op.drop_index("ix_live_calls_rc_call_id", table_name="live_calls")
    op.drop_index("ix_live_calls_session_id", table_name="live_calls")
    op.drop_index("ix_live_calls_organization_id", table_name="live_calls")
    op.drop_table("live_calls")
