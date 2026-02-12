"""add ringcentral realtime tables

Revision ID: e1f2d3c4b5a6
Revises: d7e8f9a1b2c3
Create Date: 2026-02-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e1f2d3c4b5a6"
down_revision = "d7e8f9a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ringcentral_credentials",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("rc_account_id", sa.String(length=255), nullable=True),
        sa.Column("rc_extension_id", sa.String(length=255), nullable=True),
        sa.Column("access_token_enc", sa.Text(), nullable=False),
        sa.Column("refresh_token_enc", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_ringcentral_credentials_org_user"),
    )
    op.create_index("ix_ringcentral_credentials_organization_id", "ringcentral_credentials", ["organization_id"])
    op.create_index("ix_ringcentral_credentials_user_id", "ringcentral_credentials", ["user_id"])
    op.create_index("ix_ringcentral_credentials_rc_account_id", "ringcentral_credentials", ["rc_account_id"])
    op.create_index("ix_ringcentral_credentials_rc_extension_id", "ringcentral_credentials", ["rc_extension_id"])

    op.create_table(
        "ringcentral_subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("rc_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("event_filters_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_ringcentral_subscriptions_org_user"),
        sa.CheckConstraint(
            "status in ('ACTIVE','EXPIRED','ERROR')",
            name="ck_ringcentral_subscriptions_status",
        ),
    )
    op.create_index("ix_ringcentral_subscriptions_organization_id", "ringcentral_subscriptions", ["organization_id"])
    op.create_index("ix_ringcentral_subscriptions_user_id", "ringcentral_subscriptions", ["user_id"])
    op.create_index("ix_ringcentral_subscriptions_rc_subscription_id", "ringcentral_subscriptions", ["rc_subscription_id"])
    op.create_index("ix_ringcentral_subscriptions_expires_at", "ringcentral_subscriptions", ["expires_at"])
    op.create_index("ix_ringcentral_subscriptions_status", "ringcentral_subscriptions", ["status"])

    op.create_table(
        "call_dispositions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("rc_call_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="NEW"),
        sa.Column("assigned_to_user_id", sa.String(length=36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "rc_call_id", name="uq_call_dispositions_org_call_id"),
        sa.CheckConstraint(
            "status in ('NEW','MISSED','CALLED_BACK','RESOLVED')",
            name="ck_call_dispositions_status",
        ),
    )
    op.create_index("ix_call_dispositions_organization_id", "call_dispositions", ["organization_id"])
    op.create_index("ix_call_dispositions_rc_call_id", "call_dispositions", ["rc_call_id"])
    op.create_index("ix_call_dispositions_status", "call_dispositions", ["status"])
    op.create_index("ix_call_dispositions_assigned_to_user_id", "call_dispositions", ["assigned_to_user_id"])

    op.create_table(
        "call_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("rc_call_id", sa.String(length=255), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_call_events_organization_id", "call_events", ["organization_id"])
    op.create_index("ix_call_events_type", "call_events", ["type"])
    op.create_index("ix_call_events_rc_call_id", "call_events", ["rc_call_id"])
    op.create_index("ix_call_events_received_at", "call_events", ["received_at"])


def downgrade() -> None:
    op.drop_index("ix_call_events_received_at", table_name="call_events")
    op.drop_index("ix_call_events_rc_call_id", table_name="call_events")
    op.drop_index("ix_call_events_type", table_name="call_events")
    op.drop_index("ix_call_events_organization_id", table_name="call_events")
    op.drop_table("call_events")

    op.drop_index("ix_call_dispositions_assigned_to_user_id", table_name="call_dispositions")
    op.drop_index("ix_call_dispositions_status", table_name="call_dispositions")
    op.drop_index("ix_call_dispositions_rc_call_id", table_name="call_dispositions")
    op.drop_index("ix_call_dispositions_organization_id", table_name="call_dispositions")
    op.drop_table("call_dispositions")

    op.drop_index("ix_ringcentral_subscriptions_status", table_name="ringcentral_subscriptions")
    op.drop_index("ix_ringcentral_subscriptions_expires_at", table_name="ringcentral_subscriptions")
    op.drop_index("ix_ringcentral_subscriptions_rc_subscription_id", table_name="ringcentral_subscriptions")
    op.drop_index("ix_ringcentral_subscriptions_user_id", table_name="ringcentral_subscriptions")
    op.drop_index("ix_ringcentral_subscriptions_organization_id", table_name="ringcentral_subscriptions")
    op.drop_table("ringcentral_subscriptions")

    op.drop_index("ix_ringcentral_credentials_rc_extension_id", table_name="ringcentral_credentials")
    op.drop_index("ix_ringcentral_credentials_rc_account_id", table_name="ringcentral_credentials")
    op.drop_index("ix_ringcentral_credentials_user_id", table_name="ringcentral_credentials")
    op.drop_index("ix_ringcentral_credentials_organization_id", table_name="ringcentral_credentials")
    op.drop_table("ringcentral_credentials")
