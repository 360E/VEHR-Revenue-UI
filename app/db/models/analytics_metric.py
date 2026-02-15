from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


class AnalyticsMetric(Base):
    __tablename__ = "analytics_metrics"

    metric_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    backing_view: Mapped[str] = mapped_column(String(120), nullable=False)
    allowed_roles_raw: Mapped[str] = mapped_column("allowed_roles", Text, nullable=False, default="[]")
    default_grain: Mapped[str] = mapped_column(String(32), nullable=False, default="day")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    @property
    def allowed_roles(self) -> list[str]:
        try:
            parsed = json.loads(self.allowed_roles_raw or "[]")
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [str(value).strip() for value in parsed if str(value).strip()]

    @allowed_roles.setter
    def allowed_roles(self, roles: list[str]) -> None:
        normalized = [str(value).strip() for value in roles if str(value).strip()]
        self.allowed_roles_raw = json.dumps(normalized)
