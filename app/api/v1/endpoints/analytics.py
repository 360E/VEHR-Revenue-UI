from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.deps import get_current_membership, require_permission
from app.core.rbac import normalize_role_key
from app.db.models.analytics_metric import AnalyticsMetric
from app.db.models.organization_membership import OrganizationMembership
from app.db.session import get_db
from app.services.audit import log_event

router = APIRouter(prefix="/analytics", tags=["Analytics"])

_SUPPORTED_REPORTING_VIEWS: dict[str, str] = {
    "rpt_kpi_daily": "rpt_kpi_daily",
    "rpt_kpi_snapshot": "rpt_kpi_snapshot",
    "reporting.rpt_kpi_daily": "rpt_kpi_daily",
    "reporting.rpt_kpi_snapshot": "rpt_kpi_snapshot",
}


class AnalyticsMetricRead(BaseModel):
    metric_key: str
    description: str | None = None
    backing_view: str
    default_grain: str


class AnalyticsQueryRow(BaseModel):
    date: dt.date | None = None
    as_of_ts: dt.datetime | None = None
    value_num: float
    facility_id: str | None = None
    program_id: str | None = None


class AnalyticsQueryResponse(BaseModel):
    metric_key: str
    grain: str
    rows: list[AnalyticsQueryRow]


def _normalize_metric_key(metric_key: str) -> str:
    normalized = metric_key.strip().lower()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="metric_key is required")
    return normalized


def _resolve_reporting_view(metric: AnalyticsMetric) -> str:
    key = metric.backing_view.strip().lower()
    view_name = _SUPPORTED_REPORTING_VIEWS.get(key)
    if not view_name:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metric backing_view is not mapped to a supported reporting view.",
        )
    return view_name


def _normalize_role(role: str) -> str:
    normalized = normalize_role_key(role)
    if normalized:
        return normalized
    return role.strip().lower()


def _is_role_allowed(metric: AnalyticsMetric, role: str) -> bool:
    allowed = {_normalize_role(item) for item in metric.allowed_roles if str(item).strip()}
    if not allowed:
        return False
    return _normalize_role(role) in allowed


def _as_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def _as_datetime(value: Any) -> dt.datetime | None:
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=dt.UTC)
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        if candidate.endswith("Z"):
            candidate = f"{candidate[:-1]}+00:00"
        try:
            parsed = dt.datetime.fromisoformat(candidate)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=dt.UTC)
        return parsed
    return None


def _metric_or_404(db: Session, metric_key: str) -> AnalyticsMetric:
    row = db.execute(
        select(AnalyticsMetric).where(AnalyticsMetric.metric_key == metric_key)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric key not found")
    return row


@router.get("/metrics", response_model=list[AnalyticsMetricRead])
def list_analytics_metrics(
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("analytics:view")),
) -> list[AnalyticsMetricRead]:
    rows = (
        db.execute(select(AnalyticsMetric).order_by(AnalyticsMetric.metric_key.asc()))
        .scalars()
        .all()
    )
    return [
        AnalyticsMetricRead(
            metric_key=row.metric_key,
            description=row.description,
            backing_view=row.backing_view,
            default_grain=row.default_grain,
        )
        for row in rows
        if _is_role_allowed(row, membership.role)
    ]


@router.get("/query", response_model=AnalyticsQueryResponse)
def query_analytics_metric(
    metric_key: str = Query(..., min_length=1),
    start: dt.date | None = Query(default=None),
    end: dt.date | None = Query(default=None),
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("analytics:view")),
) -> AnalyticsQueryResponse:
    normalized_metric_key = _normalize_metric_key(metric_key)
    metric = _metric_or_404(db, normalized_metric_key)
    if not _is_role_allowed(metric, membership.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Metric access denied for your role")

    view_name = _resolve_reporting_view(metric)
    org_id = membership.organization_id
    resolved_grain = metric.default_grain.strip() if metric.default_grain else "day"
    query_rows: list[AnalyticsQueryRow] = []

    if view_name == "rpt_kpi_daily":
        effective_end = end or dt.date.today()
        effective_start = start or (effective_end - dt.timedelta(days=29))
        if effective_start > effective_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start cannot be after end",
            )

        statement = text(
            f"""
            SELECT date, value_num, facility_id, program_id
            FROM {view_name}
            WHERE metric_key = :metric_key
              AND tenant_id = :tenant_id
              AND date >= :start_date
              AND date <= :end_date
            ORDER BY date ASC
            LIMIT 2000
            """
        )
        result_rows = db.execute(
            statement,
            {
                "metric_key": metric.metric_key,
                "tenant_id": org_id,
                "start_date": effective_start,
                "end_date": effective_end,
            },
        ).mappings().all()
        query_rows = [
            AnalyticsQueryRow(
                date=row.get("date"),
                value_num=_as_float(row.get("value_num")),
                facility_id=_as_text(row.get("facility_id")),
                program_id=_as_text(row.get("program_id")),
            )
            for row in result_rows
        ]
    else:
        filters = [
            "metric_key = :metric_key",
            "tenant_id = :tenant_id",
        ]
        params: dict[str, Any] = {
            "metric_key": metric.metric_key,
            "tenant_id": org_id,
        }
        if start:
            filters.append("DATE(as_of_ts) >= :start_date")
            params["start_date"] = start
        if end:
            filters.append("DATE(as_of_ts) <= :end_date")
            params["end_date"] = end

        statement = text(
            f"""
            SELECT as_of_ts, value_num, facility_id, program_id
            FROM {view_name}
            WHERE {" AND ".join(filters)}
            ORDER BY as_of_ts DESC
            LIMIT 1000
            """
        )
        result_rows = db.execute(statement, params).mappings().all()
        query_rows = [
            AnalyticsQueryRow(
                as_of_ts=_as_datetime(row.get("as_of_ts")),
                value_num=_as_float(row.get("value_num")),
                facility_id=_as_text(row.get("facility_id")),
                program_id=_as_text(row.get("program_id")),
            )
            for row in result_rows
        ]

    log_event(
        db,
        action="analytics.query",
        entity_type="analytics_metric",
        entity_id=metric.metric_key,
        organization_id=org_id,
        actor=membership.user.email,
        metadata={
            "org_id": org_id,
            "user_id": membership.user_id,
            "metric_key": metric.metric_key,
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "row_count": len(query_rows),
        },
    )

    return AnalyticsQueryResponse(
        metric_key=metric.metric_key,
        grain=resolved_grain,
        rows=query_rows,
    )
