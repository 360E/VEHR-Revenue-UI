"""add claim ledger tables

Revision ID: e8f1a2b3c4d5
Revises: d4e5f6a7b8c9
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e8f1a2b3c4d5"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # --- ENUMS (explicit creation, no implicit auto-create) ---
    claim_event_type = postgresql.ENUM(
        "SERVICE_RECORDED",
        "ERA_RECEIVED",
        "PAYMENT",
        "DENIAL",
        "ADJUSTMENT",
        name="claim_event_type",
        create_type=False,
    )

    claim_status_enum = postgresql.ENUM(
        "OPEN",
        "PARTIAL",
        "PAID",
        "DENIED",
        name="claim_status",
        create_type=False,
    )

    # Explicit safe creation
    claim_event_type.create(bind, checkfirst=True)
    claim_status_enum.create(bind, checkfirst=True)

    # --- TABLES ---
    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("resubmission_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", claim_status_enum, nullable=False),
        sa.Column("aging_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "claim_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cpt_code", sa.String(), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("billed_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "claim_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", claim_event_type, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "claim_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("total_billed", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_paid", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_allowed", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_adjusted", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("variance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", claim_status_enum, nullable=False),
        sa.Column("aging_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    bind = op.get_bind()

    op.drop_table("claim_ledger")
    op.drop_table("claim_events")
    op.drop_table("claim_lines")
    op.drop_table("claims")

    claim_event_type = postgresql.ENUM(name="claim_event_type")
    claim_status_enum = postgresql.ENUM(name="claim_status")

    claim_event_type.drop(bind, checkfirst=True)
    claim_status_enum.drop(bind, checkfirst=True)