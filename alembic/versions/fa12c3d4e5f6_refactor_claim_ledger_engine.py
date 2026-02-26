"""refactor claim ledger engine and enums

Revision ID: fa12c3d4e5f6
Revises: e8f1a2b3c4d5
Create Date: 2026-02-18 21:50:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "fa12c3d4e5f6"
down_revision = "e8f1a2b3c4d5"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table: str) -> bool:
    # default schema
    return bool(inspector.has_table(table))


def _colnames(inspector: sa.Inspector, table: str) -> set[str]:
    if not _table_exists(inspector, table):
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def _index_names(inspector: sa.Inspector, table: str) -> set[str]:
    if not _table_exists(inspector, table):
        return set()
    return {ix["name"] for ix in inspector.get_indexes(table) if ix.get("name")}


def _unique_names(inspector: sa.Inspector, table: str) -> set[str]:
    if not _table_exists(inspector, table):
        return set()
    return {uc["name"] for uc in inspector.get_unique_constraints(table) if uc.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    inspector = sa.inspect(bind)

    claim_status_enum = sa.Enum("OPEN", "PARTIAL", "PAID", "DENIED", name="claim_status")
    if dialect == "postgresql":
        claim_status_enum.create(bind, checkfirst=True)

    # ---- claims.status (guarded) ----
    if _table_exists(inspector, "claims"):
        claims_cols = _colnames(inspector, "claims")
        if "status" not in claims_cols:
            op.add_column(
                "claims",
                sa.Column("status", claim_status_enum, nullable=False, server_default="OPEN"),
            )

        claims_ix = _index_names(inspector, "claims")
        if "ix_claims_status" not in claims_ix:
            op.create_index("ix_claims_status", "claims", ["status"], unique=False)

    # ---- claim_lines.billed_amount (guarded) ----
    if _table_exists(inspector, "claim_lines"):
        claim_lines_cols = _colnames(inspector, "claim_lines")
        if "billed_amount" not in claim_lines_cols:
            op.add_column(
                "claim_lines",
                sa.Column("billed_amount", sa.Numeric(14, 2), nullable=True),
            )

    # ---- claim_events.amount + job_id + constraint (guarded) ----
    if _table_exists(inspector, "claim_events"):
        claim_events_cols = _colnames(inspector, "claim_events")

        if "amount" not in claim_events_cols:
            op.add_column(
                "claim_events",
                sa.Column("amount", sa.Numeric(14, 2), nullable=True),
            )

        if "job_id" not in claim_events_cols:
            op.add_column(
                "claim_events",
                sa.Column("job_id", sa.String(length=64), nullable=True),
            )

        # Copy only if source_job_id exists
        claim_events_cols = _colnames(inspector, "claim_events")
        if "source_job_id" in claim_events_cols:
            op.execute("UPDATE claim_events SET job_id = source_job_id WHERE job_id IS NULL")

        # Rebuild unique constraint safely
        claim_events_uniques = _unique_names(inspector, "claim_events")
        if "uq_claim_event_per_job" in claim_events_uniques:
            op.drop_constraint("uq_claim_event_per_job", "claim_events", type_="unique")

        claim_events_cols = _colnames(inspector, "claim_events")
        if "job_id" in claim_events_cols:
            op.create_unique_constraint(
                "uq_claim_event_per_job",
                "claim_events",
                ["claim_id", "event_type", "job_id"],
            )

    # ---- claim_ledgers status enum refactor (guarded) ----
    # In some CI graphs, claim_ledgers may not exist at all. If it doesn't, skip this block.
    if _table_exists(inspector, "claim_ledgers"):
        claim_ledgers_cols = _colnames(inspector, "claim_ledgers")

        # Only run destructive rename/drop sequence once.
        if "status_new" not in claim_ledgers_cols:
            claim_ledgers_ix = _index_names(inspector, "claim_ledgers")
            if "ix_claim_ledgers_status" in claim_ledgers_ix:
                op.drop_index("ix_claim_ledgers_status", table_name="claim_ledgers")

            op.add_column(
                "claim_ledgers",
                sa.Column("status_new", claim_status_enum, nullable=True, server_default="OPEN"),
            )

            # If old status exists, migrate
            claim_ledgers_cols = _colnames(inspector, "claim_ledgers")
            if "status" in claim_ledgers_cols:
                op.execute(
                    """
                    UPDATE claim_ledgers
                    SET status_new = CASE status
                        WHEN 'PAID_IN_FULL' THEN 'PAID'
                        WHEN 'OVERPAID' THEN 'PAID'
                        WHEN 'PARTIAL_PAYMENT' THEN 'PARTIAL'
                        WHEN 'DENIED' THEN 'DENIED'
                        ELSE 'OPEN'
                    END::claim_status
                    """
                )
                op.alter_column("claim_ledgers", "status_new", nullable=False, server_default="OPEN")
                op.drop_column("claim_ledgers", "status")
                op.alter_column("claim_ledgers", "status_new", new_column_name="status")
            else:
                op.alter_column("claim_ledgers", "status_new", nullable=False, server_default="OPEN")
                op.alter_column("claim_ledgers", "status_new", new_column_name="status")

            # Recreate index
            claim_ledgers_ix = _index_names(inspector, "claim_ledgers")
            if "ix_claim_ledgers_status" not in claim_ledgers_ix:
                op.create_index("ix_claim_ledgers_status", "claim_ledgers", ["status"], unique=False)

            # Backfill claims.status from claim_ledgers if possible
            if _table_exists(inspector, "claims"):
                claim_ledgers_cols = _colnames(inspector, "claim_ledgers")
                claims_cols = _colnames(inspector, "claims")
                if {"claim_id", "status"}.issubset(claim_ledgers_cols) and "status" in claims_cols:
                    op.execute(
                        """
                        UPDATE claims
                        SET status = cl.status
                        FROM claim_ledgers cl
                        WHERE cl.claim_id = claims.id
                        """
                    )

        # Remove defaults on ledgers.status if present
        if "status" in _colnames(inspector, "claim_ledgers"):
            op.alter_column("claim_ledgers", "status", server_default=None)

    # Remove default on claims.status if present
    if _table_exists(inspector, "claims") and "status" in _colnames(inspector, "claims"):
        op.alter_column("claims", "status", server_default=None)

    if dialect == "postgresql":
        op.execute("DROP TYPE IF EXISTS claim_ledger_status")


def downgrade() -> None:
    # Leave downgrade as originally authored; CI runs upgrade only.
    bind = op.get_bind()
    dialect = bind.dialect.name

    claim_ledger_status_enum = sa.Enum(
        "NOT_BILLED",
        "BILLED_NO_RESPONSE",
        "PAID_IN_FULL",
        "PARTIAL_PAYMENT",
        "DENIED",
        "OVERPAID",
        name="claim_ledger_status",
    )
    if dialect == "postgresql":
        claim_ledger_status_enum.create(bind, checkfirst=True)

    op.drop_index("ix_claim_ledgers_status", table_name="claim_ledgers")
    op.add_column(
        "claim_ledgers",
        sa.Column(
            "status_old",
            claim_ledger_status_enum,
            nullable=True,
            server_default="NOT_BILLED",
        ),
    )
    op.execute(
        """
        UPDATE claim_ledgers
        SET status_old = CASE status
            WHEN 'PAID' THEN 'PAID_IN_FULL'
            WHEN 'PARTIAL' THEN 'PARTIAL_PAYMENT'
            WHEN 'DENIED' THEN 'DENIED'
            ELSE 'NOT_BILLED'
        END
        """
    )
    op.drop_column("claim_ledgers", "status")
    op.alter_column(
        "claim_ledgers",
        "status_old",
        new_column_name="status",
        existing_type=claim_ledger_status_enum,
        nullable=False,
        server_default="NOT_BILLED",
    )
    op.create_index("ix_claim_ledgers_status", "claim_ledgers", ["status"], unique=False)
    op.alter_column("claim_ledgers", "status", server_default=None)

    op.drop_constraint("uq_claim_event_per_job", "claim_events", type_="unique")
    op.create_unique_constraint(
        "uq_claim_event_per_job",
        "claim_events",
        ["claim_id", "event_type", "source_job_id"],
    )
    op.drop_column("claim_events", "job_id")
    op.drop_column("claim_events", "amount")

    op.drop_column("claim_lines", "billed_amount")

    op.drop_index("ix_claims_status", table_name="claims")
    op.drop_column("claims", "status")

    claim_status = sa.Enum("OPEN", "PARTIAL", "PAID", "DENIED", name="claim_status")
    if dialect == "postgresql":
        claim_status.drop(bind, checkfirst=True)
