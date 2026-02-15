"""add analytics metrics registry and reporting views

Revision ID: d2b7f1c8a4e9
Revises: 0d7a2c4e9f31
Create Date: 2026-02-15 00:00:01.000000
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d2b7f1c8a4e9"
down_revision = "0d7a2c4e9f31"
branch_labels = None
depends_on = None


_METRIC_SEEDS = (
    (
        "active_patients",
        "Placeholder count of currently active patients.",
        "rpt_kpi_snapshot",
        ["admin", "office_manager", "compliance"],
        "snapshot",
    ),
    (
        "encounters_7d",
        "Placeholder 7-day encounter count.",
        "rpt_kpi_daily",
        ["admin", "office_manager", "compliance"],
        "day",
    ),
    (
        "ar_balance",
        "Placeholder accounts receivable balance.",
        "rpt_kpi_snapshot",
        ["admin", "office_manager", "billing"],
        "snapshot",
    ),
    (
        "denial_rate",
        "Placeholder claims denial rate.",
        "rpt_kpi_daily",
        ["admin", "office_manager", "billing", "compliance"],
        "day",
    ),
    (
        "unsigned_notes",
        "Placeholder unsigned note count.",
        "rpt_kpi_snapshot",
        ["admin", "office_manager", "compliance"],
        "snapshot",
    ),
)


def _create_reporting_views() -> None:
    op.execute("DROP VIEW IF EXISTS rpt_kpi_daily")
    op.execute(
        """
        CREATE VIEW rpt_kpi_daily AS
        SELECT
            CAST(NULL AS DATE) AS date,
            CAST(NULL AS VARCHAR(120)) AS metric_key,
            CAST(NULL AS DOUBLE PRECISION) AS value_num,
            CAST(NULL AS VARCHAR(36)) AS tenant_id,
            CAST(NULL AS VARCHAR(36)) AS facility_id,
            CAST(NULL AS VARCHAR(36)) AS program_id
        WHERE 1 = 0
        """
    )

    op.execute("DROP VIEW IF EXISTS rpt_kpi_snapshot")
    op.execute(
        """
        CREATE VIEW rpt_kpi_snapshot AS
        SELECT
            CAST(NULL AS TIMESTAMP) AS as_of_ts,
            CAST(NULL AS VARCHAR(120)) AS metric_key,
            CAST(NULL AS DOUBLE PRECISION) AS value_num,
            CAST(NULL AS VARCHAR(36)) AS tenant_id,
            CAST(NULL AS VARCHAR(36)) AS facility_id,
            CAST(NULL AS VARCHAR(36)) AS program_id
        WHERE 1 = 0
        """
    )


def _seed_metrics() -> None:
    conn = op.get_bind()
    for metric_key, description, backing_view, allowed_roles, default_grain in _METRIC_SEEDS:
        conn.execute(
            sa.text(
                """
                INSERT INTO analytics_metrics (
                    metric_key,
                    description,
                    backing_view,
                    allowed_roles,
                    default_grain,
                    created_at,
                    updated_at
                )
                VALUES (
                    :metric_key,
                    :description,
                    :backing_view,
                    :allowed_roles,
                    :default_grain,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT(metric_key) DO UPDATE SET
                    description = excluded.description,
                    backing_view = excluded.backing_view,
                    allowed_roles = excluded.allowed_roles,
                    default_grain = excluded.default_grain,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "metric_key": metric_key,
                "description": description,
                "backing_view": backing_view,
                "allowed_roles": json.dumps(allowed_roles),
                "default_grain": default_grain,
            },
        )


def upgrade() -> None:
    op.create_table(
        "analytics_metrics",
        sa.Column("metric_key", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("backing_view", sa.String(length=120), nullable=False),
        sa.Column("allowed_roles", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("default_grain", sa.String(length=32), nullable=False, server_default=sa.text("'day'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("metric_key"),
    )
    _create_reporting_views()
    _seed_metrics()


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS rpt_kpi_snapshot")
    op.execute("DROP VIEW IF EXISTS rpt_kpi_daily")
    op.drop_table("analytics_metrics")
