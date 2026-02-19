"""add pdf template registry

Revision ID: 2c4d6e8f1234
Revises: 1f2a3b4c5d6e
Create Date: 2026-02-19 08:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "2c4d6e8f1234"
down_revision = "1f2a3b4c5d6e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    json_type = postgresql.JSONB(astext_type=sa.Text()) if dialect == "postgresql" else sa.JSON()
    json_obj_default = sa.text("'{}'::jsonb") if dialect == "postgresql" else sa.text("'{}'")
    json_array_default = sa.text("'[]'::jsonb") if dialect == "postgresql" else sa.text("'[]'")
    doc_kind_enum = postgresql.ENUM("EOB", "REMITTANCE", "DENIAL", "UNKNOWN", name="pdf_document_kind", create_type=False)
    if dialect == "postgresql":
        doc_kind_enum.create(bind, checkfirst=True)

    op.create_table(
        "pdf_template_registry",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("payer_id", sa.String(length=36), nullable=True),
        sa.Column("template_name", sa.String(length=200), nullable=False),
        sa.Column("document_kind", doc_kind_enum, nullable=False),
        sa.Column("signature_version", sa.String(length=50), nullable=False),
        sa.Column("signature_rules", json_type, nullable=False, server_default=json_obj_default),
        sa.Column("anchor_hints", json_type, nullable=False, server_default=json_obj_default),
        sa.Column("required_fields", json_type, nullable=False, server_default=json_array_default),
        sa.Column("confidence_thresholds", json_type, nullable=False, server_default=json_obj_default),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_pdf_template_registry_payer_id", "pdf_template_registry", ["payer_id"], unique=False)
    op.create_index("ix_pdf_template_registry_active", "pdf_template_registry", ["active"], unique=False)
    op.create_index("ix_pdf_template_registry_document_kind", "pdf_template_registry", ["document_kind"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.drop_index("ix_pdf_template_registry_document_kind", table_name="pdf_template_registry")
    op.drop_index("ix_pdf_template_registry_active", table_name="pdf_template_registry")
    op.drop_index("ix_pdf_template_registry_payer_id", table_name="pdf_template_registry")
    op.drop_table("pdf_template_registry")

    if dialect == "postgresql":
        sa.Enum(name="pdf_document_kind").drop(bind, checkfirst=True)
