"""harden revenue era constraints and indexes

Revision ID: 1d2f3c4b5a67
Revises: 0f7e3d2c1b45
Create Date: 2026-02-19 20:45:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1d2f3c4b5a67"
down_revision = "0f7e3d2c1b45"
branch_labels = None
depends_on = None


def _dedupe(table: str, partition_cols: list[str], order_cols: list[str]) -> None:
    partition = ", ".join(partition_cols)
    ordering = ", ".join(order_cols)
    op.execute(
        sa.text(
            f"""
            DELETE FROM {table} AS t
            USING (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY {partition} ORDER BY {ordering}) AS rn
                FROM {table}
            ) AS ranked
            WHERE ranked.rn > 1 AND t.id = ranked.id
            """
        )
    )


def upgrade() -> None:
    _dedupe(
        "revenue_era_extract_results",
        ["era_file_id"],
        ["extracted_at DESC", "id DESC"],
    )
    _dedupe(
        "revenue_era_structured_results",
        ["era_file_id"],
        ["created_at DESC", "id DESC"],
    )
    _dedupe(
        "revenue_era_work_items",
        ["era_file_id", "claim_ref"],
        ["created_at DESC", "id DESC"],
    )
    _dedupe(
        "revenue_era_claim_lines",
        ["era_file_id", "claim_ref", "service_date", "proc_code"],
        ["created_at DESC", "id DESC"],
    )

    op.drop_index("ix_revenue_era_extract_results_file", table_name="revenue_era_extract_results")
    op.create_unique_constraint(
        "uq_revenue_era_extract_results_file",
        "revenue_era_extract_results",
        ["era_file_id"],
    )

    op.drop_index("ix_revenue_era_structured_results_file", table_name="revenue_era_structured_results")
    op.create_unique_constraint(
        "uq_revenue_era_structured_results_file",
        "revenue_era_structured_results",
        ["era_file_id"],
    )

    op.create_unique_constraint(
        "uq_revenue_era_work_items_file_claim",
        "revenue_era_work_items",
        ["era_file_id", "claim_ref"],
    )
    op.create_index(
        "ix_revenue_era_work_items_dollars_cents_desc",
        "revenue_era_work_items",
        [sa.text("dollars_cents DESC")],
        unique=False,
    )

    op.create_unique_constraint(
        "uq_revenue_era_claim_lines_claim_key",
        "revenue_era_claim_lines",
        ["era_file_id", "claim_ref", "service_date", "proc_code"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_revenue_era_claim_lines_claim_key", "revenue_era_claim_lines", type_="unique")
    op.drop_index("ix_revenue_era_work_items_dollars_cents_desc", table_name="revenue_era_work_items")
    op.drop_constraint("uq_revenue_era_work_items_file_claim", "revenue_era_work_items", type_="unique")

    op.drop_constraint("uq_revenue_era_structured_results_file", "revenue_era_structured_results", type_="unique")
    op.create_index(
        "ix_revenue_era_structured_results_file",
        "revenue_era_structured_results",
        ["era_file_id"],
        unique=False,
    )

    op.drop_constraint("uq_revenue_era_extract_results_file", "revenue_era_extract_results", type_="unique")
    op.create_index(
        "ix_revenue_era_extract_results_file",
        "revenue_era_extract_results",
        ["era_file_id"],
        unique=False,
    )
