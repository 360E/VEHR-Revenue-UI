"""add form template description

Revision ID: d4f3b2a1c9e0
Revises: c1a9e8b7d6f4
Create Date: 2026-02-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4f3b2a1c9e0"
down_revision = "c1a9e8b7d6f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "form_templates",
        sa.Column("description", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("form_templates", "description")

