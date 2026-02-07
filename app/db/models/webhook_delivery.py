from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_outbox_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("event_outbox.id"),
        nullable=False,
    )
    webhook_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("webhook_endpoints.id"),
        nullable=False,
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    event: Mapped["EventOutbox"] = relationship(
        "EventOutbox",
        back_populates="deliveries",
    )
    webhook: Mapped["WebhookEndpoint"] = relationship(
        "WebhookEndpoint",
        back_populates="deliveries",
    )
