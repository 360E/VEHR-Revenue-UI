from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.base import Base


class RingCentralSubscription(Base):
    __tablename__ = "ringcentral_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_ringcentral_subscriptions_org_user",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    rc_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    event_filters_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="ringcentral_subscriptions",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="ringcentral_subscriptions",
    )
