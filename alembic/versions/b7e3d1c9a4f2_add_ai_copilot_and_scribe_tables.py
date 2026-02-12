"""add ai copilot and scribe tables

Revision ID: b7e3d1c9a4f2
Revises: a12f6d9c4e7b
Create Date: 2026-02-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7e3d1c9a4f2"
down_revision = "a12f6d9c4e7b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_threads",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_ai_threads_org_id_id"),
    )
    op.create_index("ix_ai_threads_organization_id", "ai_threads", ["organization_id"])
    op.create_index("ix_ai_threads_user_id", "ai_threads", ["user_id"])
    op.create_index("ix_ai_threads_updated_at", "ai_threads", ["updated_at"])

    op.create_table(
        "ai_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("thread_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["thread_id"], ["ai_threads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_messages_thread_id", "ai_messages", ["thread_id"])
    op.create_index("ix_ai_messages_role", "ai_messages", ["role"])
    op.create_index("ix_ai_messages_created_at", "ai_messages", ["created_at"])

    op.create_table(
        "scribe_captures",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("encounter_id", sa.String(length=36), nullable=False),
        sa.Column("s3_key", sa.String(length=500), nullable=False),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scribe_captures_organization_id", "scribe_captures", ["organization_id"])
    op.create_index("ix_scribe_captures_user_id", "scribe_captures", ["user_id"])
    op.create_index("ix_scribe_captures_encounter_id", "scribe_captures", ["encounter_id"])
    op.create_index("ix_scribe_captures_created_at", "scribe_captures", ["created_at"])
    op.create_index("ix_scribe_captures_deleted_at", "scribe_captures", ["deleted_at"])

    op.create_table(
        "scribe_transcripts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("capture_id", sa.String(length=36), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["capture_id"], ["scribe_captures.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scribe_transcripts_capture_id", "scribe_transcripts", ["capture_id"])
    op.create_index("ix_scribe_transcripts_created_at", "scribe_transcripts", ["created_at"])

    op.create_table(
        "scribe_note_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("capture_id", sa.String(length=36), nullable=False),
        sa.Column("note_type", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("note_type in ('SOAP','DAP')", name="ck_scribe_note_drafts_note_type"),
        sa.ForeignKeyConstraint(["capture_id"], ["scribe_captures.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scribe_note_drafts_capture_id", "scribe_note_drafts", ["capture_id"])
    op.create_index("ix_scribe_note_drafts_note_type", "scribe_note_drafts", ["note_type"])
    op.create_index("ix_scribe_note_drafts_created_at", "scribe_note_drafts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_scribe_note_drafts_created_at", table_name="scribe_note_drafts")
    op.drop_index("ix_scribe_note_drafts_note_type", table_name="scribe_note_drafts")
    op.drop_index("ix_scribe_note_drafts_capture_id", table_name="scribe_note_drafts")
    op.drop_table("scribe_note_drafts")

    op.drop_index("ix_scribe_transcripts_created_at", table_name="scribe_transcripts")
    op.drop_index("ix_scribe_transcripts_capture_id", table_name="scribe_transcripts")
    op.drop_table("scribe_transcripts")

    op.drop_index("ix_scribe_captures_deleted_at", table_name="scribe_captures")
    op.drop_index("ix_scribe_captures_created_at", table_name="scribe_captures")
    op.drop_index("ix_scribe_captures_encounter_id", table_name="scribe_captures")
    op.drop_index("ix_scribe_captures_user_id", table_name="scribe_captures")
    op.drop_index("ix_scribe_captures_organization_id", table_name="scribe_captures")
    op.drop_table("scribe_captures")

    op.drop_index("ix_ai_messages_created_at", table_name="ai_messages")
    op.drop_index("ix_ai_messages_role", table_name="ai_messages")
    op.drop_index("ix_ai_messages_thread_id", table_name="ai_messages")
    op.drop_table("ai_messages")

    op.drop_index("ix_ai_threads_updated_at", table_name="ai_threads")
    op.drop_index("ix_ai_threads_user_id", table_name="ai_threads")
    op.drop_index("ix_ai_threads_organization_id", table_name="ai_threads")
    op.drop_table("ai_threads")
