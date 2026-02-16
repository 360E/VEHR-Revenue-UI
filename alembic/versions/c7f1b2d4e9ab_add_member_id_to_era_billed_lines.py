"""add member_id to era and billed lines

Revision ID: c7f1b2d4e9ab
Revises: b2d4e7f9c8a1
Create Date: 2026-02-16 10:58:00
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c7f1b2d4e9ab"
down_revision = "b2d4e7f9c8a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("era_lines", sa.Column("member_id", sa.Text(), nullable=True))
    op.add_column("billed_lines", sa.Column("member_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("billed_lines", "member_id")
    op.drop_column("era_lines", "member_id")
