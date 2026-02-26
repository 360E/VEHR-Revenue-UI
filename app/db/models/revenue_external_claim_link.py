from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from app.core.time import utc_now
from app.db.base import Base


class RevenueExternalClaimLink(Base):
    __tablename__ = "revenue_external_claim_links"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "external_system",
            "external_claim_id",
            name="uq_revenue_external_claim_links_org_system_claim",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    external_system: Mapped[str] = mapped_column(String(100), nullable=False)
    external_claim_id: Mapped[str] = mapped_column(String(255), nullable=False)
    era_file_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("revenue_era_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    claim_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=expression.text("CURRENT_TIMESTAMP"),
    )
