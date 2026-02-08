"""add clinical audit contract tables

Revision ID: c1a9e8b7d6f4
Revises: 9c1e2d4a5f6b
Create Date: 2026-02-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c1a9e8b7d6f4"
down_revision = "9c1e2d4a5f6b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_events", sa.Column("metadata_json", sa.Text(), nullable=True))

    op.create_table(
        "clinical_audit_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("triggered_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("subject_type", sa.String(length=50), nullable=False),
        sa.Column("subject_id", sa.String(length=100), nullable=False),
        sa.Column("related_entities_json", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_clinical_audit_runs_organization_id",
        "clinical_audit_runs",
        ["organization_id"],
    )

    op.create_table(
        "clinical_audit_findings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("signal_type", sa.String(length=80), nullable=False),
        sa.Column("subject_type", sa.String(length=50), nullable=False),
        sa.Column("subject_id", sa.String(length=100), nullable=False),
        sa.Column("related_entities_json", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("finding_summary", sa.Text(), nullable=False),
        sa.Column("evidence_references_json", sa.Text(), nullable=False),
        sa.Column("suggested_correction", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["clinical_audit_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_clinical_audit_findings_organization_id",
        "clinical_audit_findings",
        ["organization_id"],
    )
    op.create_index(
        "ix_clinical_audit_findings_run_id",
        "clinical_audit_findings",
        ["run_id"],
    )

    op.create_table(
        "review_queue_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("subject_type", sa.String(length=50), nullable=False),
        sa.Column("subject_id", sa.String(length=100), nullable=False),
        sa.Column("source_finding_id", sa.String(length=36), nullable=True),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("assigned_to_user_id", sa.String(length=36), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["source_finding_id"], ["clinical_audit_findings.id"]),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_finding_id", name="uq_review_queue_source_finding"),
    )
    op.create_index(
        "ix_review_queue_items_organization_id",
        "review_queue_items",
        ["organization_id"],
    )

    op.create_table(
        "review_actions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("queue_item_id", sa.String(length=36), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["queue_item_id"], ["review_queue_items.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_review_actions_organization_id",
        "review_actions",
        ["organization_id"],
    )
    op.create_index(
        "ix_review_actions_queue_item_id",
        "review_actions",
        ["queue_item_id"],
    )

    op.create_table(
        "review_evidence_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("queue_item_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["queue_item_id"], ["review_queue_items.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "queue_item_id",
            "document_id",
            name="uq_review_evidence_queue_document",
        ),
    )
    op.create_index(
        "ix_review_evidence_links_organization_id",
        "review_evidence_links",
        ["organization_id"],
    )
    op.create_index(
        "ix_review_evidence_links_queue_item_id",
        "review_evidence_links",
        ["queue_item_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_review_evidence_links_queue_item_id", table_name="review_evidence_links")
    op.drop_index("ix_review_evidence_links_organization_id", table_name="review_evidence_links")
    op.drop_table("review_evidence_links")

    op.drop_index("ix_review_actions_queue_item_id", table_name="review_actions")
    op.drop_index("ix_review_actions_organization_id", table_name="review_actions")
    op.drop_table("review_actions")

    op.drop_index("ix_review_queue_items_organization_id", table_name="review_queue_items")
    op.drop_table("review_queue_items")

    op.drop_index("ix_clinical_audit_findings_run_id", table_name="clinical_audit_findings")
    op.drop_index("ix_clinical_audit_findings_organization_id", table_name="clinical_audit_findings")
    op.drop_table("clinical_audit_findings")

    op.drop_index("ix_clinical_audit_runs_organization_id", table_name="clinical_audit_runs")
    op.drop_table("clinical_audit_runs")

    op.drop_column("audit_events", "metadata_json")
