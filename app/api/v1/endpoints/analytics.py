from __future__ import annotations

import datetime as dt
import logging
import re
import time
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_membership, require_permission
from app.core.rbac import normalize_role_key
from app.db.models.analytics_ai_audit_log import AnalyticsAiAuditLog
from app.db.models.analytics_alert import AnalyticsAlert
from app.db.models.analytics_metric import AnalyticsMetric
from app.db.models.organization_membership import OrganizationMembership
from app.db.models.rpt_kpi_daily import RptKpiDaily
from app.db.models.rpt_kpi_snapshot import RptKpiSnapshot
from app.db.session import get_db
from app.services.audit import log_event
from app.services.ttl_cache import TtlLruCache

router = APIRouter(prefix="/analytics", tags=["Analytics"])
logger = logging.getLogger(__name__)

_DAILY_GRAIN = "daily"
_SNAPSHOT_GRAIN = "snapshot"
_DAILY_TABLE = "rpt_kpi_daily"
_SNAPSHOT_TABLE = "rpt_kpi_snapshot"

_ANALYTICS_QUERY_CACHE_TTL_SECONDS = 60.0
_ANALYTICS_QUERY_CACHE_MAXSIZE = 512
_ANALYTICS_QUERY_CACHE = TtlLruCache(
    ttl_seconds=_ANALYTICS_QUERY_CACHE_TTL_SECONDS,
    maxsize=_ANALYTICS_QUERY_CACHE_MAXSIZE,
)

_CACHE_BYPASS_HEADER = "x-cache-bypass"


class AnalyticsMetricRead(BaseModel):
    metric_key: str
    description: str | None = None
    category: str
    grain: str
    backing_table: str


class AnalyticsQueryRow(BaseModel):
    kpi_date: dt.date | None = None
    as_of_ts: dt.datetime | None = None
    value_num: float | None = None
    value_json: dict | list | None = None
    facility_id: str | None = None
    program_id: str | None = None
    provider_id: str | None = None
    payer_id: str | None = None


class AnalyticsQueryResponse(BaseModel):
    metric_key: str
    grain: str
    start: dt.date | None = None
    end: dt.date | None = None
    rows: list[AnalyticsQueryRow]


class AnalyticsAlertRead(BaseModel):
    id: str
    organization_id: str
    alert_type: str
    metric_key: str | None = None
    report_key: str | None = None
    baseline_window_days: int
    comparison_period: str
    current_range_start: dt.date
    current_range_end: dt.date
    baseline_range_start: dt.date
    baseline_range_end: dt.date
    current_value: float
    baseline_value: float
    delta_value: float
    delta_pct: float | None = None
    severity: str
    title: str
    summary: str
    recommended_actions: list[str] = []
    context_filters: dict | None = None
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime
    acknowledged_at: dt.datetime | None = None
    resolved_at: dt.datetime | None = None
    dedupe_key: str


_ALERT_STATUSES = {"open", "acknowledged", "resolved"}
_ALERT_SEVERITY_ORDER = {
    "info": 1,
    "low": 2,
    "medium": 3,
    "high": 4,
    "critical": 5,
}


def _normalize_metric_key(metric_key: str) -> str:
    normalized = metric_key.strip().lower()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="metric_key is required")
    return normalized


def _normalize_role(role: str) -> str:
    normalized = normalize_role_key(role)
    return normalized or role.strip().lower()


def _is_role_allowed(metric: AnalyticsMetric, role: str) -> bool:
    allowed = {_normalize_role(str(item)) for item in (metric.allowed_roles or []) if str(item).strip()}
    return _normalize_role(role) in allowed


def _metric_or_404(db: Session, metric_key: str) -> AnalyticsMetric:
    row = db.execute(
        select(AnalyticsMetric).where(AnalyticsMetric.metric_key == metric_key)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric key not found")
    return row


def _uuid_string_or_400(value: str, *, field_name: str) -> str:
    try:
        return str(UUID(str(value)))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}. Expected UUID string.",
        ) from exc


def _optional_uuid_filter(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    return _uuid_string_or_400(candidate, field_name=field_name)


def _decimal_to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _cache_bypass_requested(request: Request) -> bool:
    raw = request.headers.get(_CACHE_BYPASS_HEADER, "").strip().lower()
    return raw in {"1", "true", "yes"}


def _cache_bypass_allowed(role: str) -> bool:
    normalized = _normalize_role(role)
    return normalized in {"admin", "office_manager", "sud_supervisor"}


def _analytics_cache_key(
    *,
    tenant_id: str,
    role: str,
    metric: AnalyticsMetric,
    start: dt.date | None,
    end: dt.date | None,
    facility_id: str | None,
    program_id: str | None,
    provider_id: str | None,
    payer_id: str | None,
) -> str:
    return "|".join(
        [
            "analytics.query.v1",
            tenant_id,
            _normalize_role(role),
            metric.metric_key,
            str(metric.grain),
            str(metric.backing_table),
            start.isoformat() if start else "",
            end.isoformat() if end else "",
            facility_id or "",
            program_id or "",
            provider_id or "",
            payer_id or "",
        ]
    )


def _normalize_alert_status(value: str) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status is required")
    if normalized not in _ALERT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Expected one of: {', '.join(sorted(_ALERT_STATUSES))}",
        )
    return normalized


def _severity_min_filter(value: str) -> set[str]:
    normalized = (value or "").strip().lower()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="severity_min is required")
    min_rank = _ALERT_SEVERITY_ORDER.get(normalized)
    if min_rank is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid severity_min. Expected one of: {', '.join(sorted(_ALERT_SEVERITY_ORDER.keys()))}",
        )
    return {sev for sev, rank in _ALERT_SEVERITY_ORDER.items() if rank >= min_rank}


def _serialize_alert(row: AnalyticsAlert) -> AnalyticsAlertRead:
    return AnalyticsAlertRead(
        id=row.id,
        organization_id=row.organization_id,
        alert_type=row.alert_type,
        metric_key=row.metric_key,
        report_key=row.report_key,
        baseline_window_days=row.baseline_window_days,
        comparison_period=row.comparison_period,
        current_range_start=row.current_range_start,
        current_range_end=row.current_range_end,
        baseline_range_start=row.baseline_range_start,
        baseline_range_end=row.baseline_range_end,
        current_value=_decimal_to_float(row.current_value) or 0.0,
        baseline_value=_decimal_to_float(row.baseline_value) or 0.0,
        delta_value=_decimal_to_float(row.delta_value) or 0.0,
        delta_pct=_decimal_to_float(row.delta_pct),
        severity=row.severity,
        title=row.title,
        summary=row.summary,
        recommended_actions=[str(item) for item in (row.recommended_actions or [])],
        context_filters=row.context_filters or {},
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        acknowledged_at=row.acknowledged_at,
        resolved_at=row.resolved_at,
        dedupe_key=row.dedupe_key,
    )


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
            category=row.category,
            grain=row.grain,
            backing_table=row.backing_table,
        )
        for row in rows
        if _is_role_allowed(row, membership.role)
    ]


@router.get("/query", response_model=AnalyticsQueryResponse)
def query_analytics_metric(
    request: Request,
    metric_key: str = Query(..., min_length=1),
    start: dt.date | None = Query(default=None),
    end: dt.date | None = Query(default=None),
    facility_id: str | None = Query(default=None),
    program_id: str | None = Query(default=None),
    provider_id: str | None = Query(default=None),
    payer_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("analytics:view")),
) -> AnalyticsQueryResponse:
    t0 = time.perf_counter()
    if start and end and start > end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start cannot be after end")

    normalized_metric_key = _normalize_metric_key(metric_key)
    metric = _metric_or_404(db, normalized_metric_key)
    if not _is_role_allowed(metric, membership.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Metric access denied for your role")

    tenant_id = _uuid_string_or_400(membership.organization_id, field_name="organization_id")
    facility_filter = _optional_uuid_filter(facility_id, field_name="facility_id")
    program_filter = _optional_uuid_filter(program_id, field_name="program_id")
    provider_filter = _optional_uuid_filter(provider_id, field_name="provider_id")
    payer_filter = _optional_uuid_filter(payer_id, field_name="payer_id")

    cache_key = _analytics_cache_key(
        tenant_id=tenant_id,
        role=membership.role,
        metric=metric,
        start=start,
        end=end,
        facility_id=facility_filter,
        program_id=program_filter,
        provider_id=provider_filter,
        payer_id=payer_filter,
    )
    bypass_cache = _cache_bypass_requested(request) and _cache_bypass_allowed(membership.role)

    if not bypass_cache:
        cached, hit = _ANALYTICS_QUERY_CACHE.get(cache_key)
        if hit and isinstance(cached, AnalyticsQueryResponse):
            duration_ms = int((time.perf_counter() - t0) * 1000)
            logger.info(
                "analytics.query cache_hit=1 metric_key=%s org_id=%s duration_ms=%s rows=%s",
                metric.metric_key,
                tenant_id,
                duration_ms,
                len(cached.rows),
            )
            log_event(
                db,
                action="analytics.query",
                entity_type="analytics_metric",
                entity_id=metric.metric_key,
                organization_id=tenant_id,
                actor=membership.user.email,
                metadata={
                    "org_id": tenant_id,
                    "user_id": membership.user_id,
                    "metric_key": metric.metric_key,
                    "start": start.isoformat() if start else None,
                    "end": end.isoformat() if end else None,
                    "facility_id": facility_filter,
                    "program_id": program_filter,
                    "provider_id": provider_filter,
                    "payer_id": payer_filter,
                    "row_count": len(cached.rows),
                    "cache": {"hit": True, "bypass": False},
                    "duration_ms": duration_ms,
                },
            )
            return cached

    query_rows: list[AnalyticsQueryRow] = []

    if metric.grain == _DAILY_GRAIN and metric.backing_table == _DAILY_TABLE:
        query = select(RptKpiDaily).where(
            RptKpiDaily.tenant_id == tenant_id,
            RptKpiDaily.metric_key == metric.metric_key,
        )
        if start:
            query = query.where(RptKpiDaily.kpi_date >= start)
        if end:
            query = query.where(RptKpiDaily.kpi_date <= end)
        if facility_filter:
            query = query.where(RptKpiDaily.facility_id == facility_filter)
        if program_filter:
            query = query.where(RptKpiDaily.program_id == program_filter)
        if provider_filter:
            query = query.where(RptKpiDaily.provider_id == provider_filter)
        if payer_filter:
            query = query.where(RptKpiDaily.payer_id == payer_filter)

        rows = (
            db.execute(query.order_by(RptKpiDaily.kpi_date.asc()).limit(5000))
            .scalars()
            .all()
        )
        query_rows = [
            AnalyticsQueryRow(
                kpi_date=row.kpi_date,
                value_num=_decimal_to_float(row.value_num),
                value_json=row.value_json,
                facility_id=row.facility_id,
                program_id=row.program_id,
                provider_id=row.provider_id,
                payer_id=row.payer_id,
            )
            for row in rows
        ]
    elif metric.grain == _SNAPSHOT_GRAIN and metric.backing_table == _SNAPSHOT_TABLE:
        query = select(RptKpiSnapshot).where(
            RptKpiSnapshot.tenant_id == tenant_id,
            RptKpiSnapshot.metric_key == metric.metric_key,
        )
        if start:
            query = query.where(func.date(RptKpiSnapshot.as_of_ts) >= start)
        if end:
            query = query.where(func.date(RptKpiSnapshot.as_of_ts) <= end)
        if facility_filter:
            query = query.where(RptKpiSnapshot.facility_id == facility_filter)
        if program_filter:
            query = query.where(RptKpiSnapshot.program_id == program_filter)
        if provider_filter:
            query = query.where(RptKpiSnapshot.provider_id == provider_filter)
        if payer_filter:
            query = query.where(RptKpiSnapshot.payer_id == payer_filter)

        rows = (
            db.execute(query.order_by(RptKpiSnapshot.as_of_ts.asc()).limit(5000))
            .scalars()
            .all()
        )
        query_rows = [
            AnalyticsQueryRow(
                as_of_ts=row.as_of_ts,
                value_num=_decimal_to_float(row.value_num),
                value_json=row.value_json,
                facility_id=row.facility_id,
                program_id=row.program_id,
                provider_id=row.provider_id,
                payer_id=row.payer_id,
            )
            for row in rows
        ]
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metric configuration is invalid. Expected supported grain/backing_table mapping.",
        )

    log_event(
        db,
        action="analytics.query",
        entity_type="analytics_metric",
        entity_id=metric.metric_key,
        organization_id=tenant_id,
        actor=membership.user.email,
        metadata={
            "org_id": tenant_id,
            "user_id": membership.user_id,
            "metric_key": metric.metric_key,
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "facility_id": facility_filter,
            "program_id": program_filter,
            "provider_id": provider_filter,
            "payer_id": payer_filter,
            "row_count": len(query_rows),
            "cache": {"hit": False, "bypass": bypass_cache},
            "duration_ms": int((time.perf_counter() - t0) * 1000),
        },
    )

    response = AnalyticsQueryResponse(
        metric_key=metric.metric_key,
        grain=metric.grain,
        start=start,
        end=end,
        rows=query_rows,
    )

    if not bypass_cache:
        _ANALYTICS_QUERY_CACHE.set(cache_key, response)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            "analytics.query cache_hit=0 metric_key=%s org_id=%s duration_ms=%s rows=%s",
            metric.metric_key,
            tenant_id,
            duration_ms,
            len(query_rows),
        )

    return response


@router.get("/alerts", response_model=list[AnalyticsAlertRead])
def list_analytics_alerts(
    status_filter: str | None = Query(default=None, alias="status"),
    report_key: str | None = Query(default=None),
    severity_min: str | None = Query(default=None),
    since: dt.datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("analytics:view")),
) -> list[AnalyticsAlertRead]:
    tenant_id = _uuid_string_or_400(membership.organization_id, field_name="organization_id")

    query = select(AnalyticsAlert).where(AnalyticsAlert.organization_id == tenant_id)

    if status_filter and status_filter.strip():
        normalized = _normalize_alert_status(status_filter)
        query = query.where(AnalyticsAlert.status == normalized)
    if report_key and report_key.strip():
        query = query.where(AnalyticsAlert.report_key == report_key.strip().lower())
    if severity_min and severity_min.strip():
        allowed = _severity_min_filter(severity_min)
        query = query.where(AnalyticsAlert.severity.in_(sorted(allowed)))
    if since:
        query = query.where(AnalyticsAlert.created_at >= since)

    rows = (
        db.execute(
            query.order_by(AnalyticsAlert.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [_serialize_alert(row) for row in rows]


@router.post("/alerts/{alert_id}/acknowledge", response_model=AnalyticsAlertRead)
def acknowledge_analytics_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("analytics:view")),
) -> AnalyticsAlertRead:
    tenant_id = _uuid_string_or_400(membership.organization_id, field_name="organization_id")
    alert_uuid = _uuid_string_or_400(alert_id, field_name="alert_id")

    row = db.execute(
        select(AnalyticsAlert).where(
            AnalyticsAlert.id == alert_uuid,
            AnalyticsAlert.organization_id == tenant_id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    normalized_status = _normalize_alert_status(row.status)
    if normalized_status != "acknowledged":
        row.status = "acknowledged"
        if row.acknowledged_at is None:
            row.acknowledged_at = dt.datetime.now(dt.UTC)
        db.add(row)
        db.commit()
        db.refresh(row)

    log_event(
        db,
        action="analytics.alert_acknowledged",
        entity_type="analytics_alert",
        entity_id=row.id,
        organization_id=tenant_id,
        actor=membership.user.email,
        metadata={
            "org_id": tenant_id,
            "user_id": membership.user_id,
            "alert_id": row.id,
            "dedupe_key": row.dedupe_key,
        },
    )
    return _serialize_alert(row)


@router.post("/alerts/{alert_id}/resolve", response_model=AnalyticsAlertRead)
def resolve_analytics_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("analytics:view")),
) -> AnalyticsAlertRead:
    tenant_id = _uuid_string_or_400(membership.organization_id, field_name="organization_id")
    alert_uuid = _uuid_string_or_400(alert_id, field_name="alert_id")

    row = db.execute(
        select(AnalyticsAlert).where(
            AnalyticsAlert.id == alert_uuid,
            AnalyticsAlert.organization_id == tenant_id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    normalized_status = _normalize_alert_status(row.status)
    if normalized_status != "resolved":
        row.status = "resolved"
        if row.resolved_at is None:
            row.resolved_at = dt.datetime.now(dt.UTC)
        db.add(row)
        db.commit()
        db.refresh(row)

    log_event(
        db,
        action="analytics.alert_resolved",
        entity_type="analytics_alert",
        entity_id=row.id,
        organization_id=tenant_id,
        actor=membership.user.email,
        metadata={
            "org_id": tenant_id,
            "user_id": membership.user_id,
            "alert_id": row.id,
            "dedupe_key": row.dedupe_key,
        },
    )
    return _serialize_alert(row)


class AnalyticsAiFilters(BaseModel):
    start: dt.date | None = None
    end: dt.date | None = None
    facility_id: str | None = None
    program_id: str | None = None
    provider_id: str | None = None
    payer_id: str | None = None


class AnalyticsAiQueryRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)
    report_key: str | None = None
    filters: AnalyticsAiFilters | None = None


class AnalyticsAiEvidenceMetric(BaseModel):
    metric_key: str
    label: str
    grain: str
    current_range_start: dt.date
    current_range_end: dt.date
    baseline_range_start: dt.date
    baseline_range_end: dt.date
    current_value: float | None = None
    baseline_value: float | None = None
    delta_value: float | None = None
    delta_pct: float | None = None
    error: str | None = None


class AnalyticsAiQueryResponse(BaseModel):
    answer: str
    metrics_used: list[str]
    filters_applied: dict
    next_step_tasks: list[str]
    evidence: list[AnalyticsAiEvidenceMetric] = Field(default_factory=list)


class AnalyticsAiAuditLogRead(BaseModel):
    id: str
    organization_id: str
    membership_id: str
    user_id: str
    report_key: str | None = None
    conversation_id: str
    message_id: str
    user_prompt: str
    intent: str
    rationale: str
    metrics_used: list[str]
    filters_applied: dict
    query_requests: list[dict]
    query_responses_summary: dict
    created_at: dt.datetime


_REPORT_CATEGORY_BY_KEY: dict[str, str] = {
    "executive_overview": "executive",
    "exec_overview": "executive",
    "revenue_cycle": "revenue",
    "clinical_delivery": "clinical",
    "compliance_risk": "compliance",
    "chart_audit": "compliance",
}

_REPORT_CATEGORY_TO_METRIC_CATEGORIES: dict[str, set[str]] = {
    "revenue": {"financial"},
    "clinical": {"operations"},
    "compliance": {"compliance"},
}

_DEFAULT_METRICS_BY_REPORT_KEY: dict[str, list[str]] = {
    "chart_audit": ["unsigned_notes_over_24h", "unsigned_notes_over_72h", "active_clients", "encounters_week"],
    "executive_overview": [
        "active_clients",
        "encounters_week",
        "charges_week",
        "claims_paid_week",
        "denial_rate_week",
        "unsigned_notes_over_72h",
    ],
    "exec_overview": [
        "active_clients",
        "encounters_week",
        "charges_week",
        "claims_paid_week",
        "denial_rate_week",
        "unsigned_notes_over_72h",
    ],
    "revenue_cycle": [
        "charges_week",
        "claims_submitted_week",
        "claims_paid_week",
        "denial_rate_week",
        "ar_balance_total",
        "ar_over_30",
    ],
    "clinical_delivery": [
        "encounters_week",
        "active_clients",
        "attendance_rate_week",
        "no_show_rate_week",
        "new_admissions_week",
        "discharges_week",
    ],
    "compliance_risk": ["unsigned_notes_over_24h", "unsigned_notes_over_72h", "active_clients", "denial_rate_week"],
}

_KEYWORD_METRIC_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(census|active)", re.IGNORECASE), "active_clients"),
    (re.compile(r"encounter", re.IGNORECASE), "encounters_week"),
    (re.compile(r"charge", re.IGNORECASE), "charges_week"),
    (re.compile(r"(paid|payment)", re.IGNORECASE), "claims_paid_week"),
    (re.compile(r"submit", re.IGNORECASE), "claims_submitted_week"),
    (re.compile(r"denial", re.IGNORECASE), "denial_rate_week"),
    (re.compile(r"(accounts receivable|\\bar\\b)", re.IGNORECASE), "ar_balance_total"),
    (re.compile(r"unsigned", re.IGNORECASE), "unsigned_notes_over_72h"),
    (re.compile(r"admission", re.IGNORECASE), "new_admissions_week"),
    (re.compile(r"discharge", re.IGNORECASE), "discharges_week"),
    (re.compile(r"no\\s*show", re.IGNORECASE), "no_show_rate_week"),
    (re.compile(r"attendance", re.IGNORECASE), "attendance_rate_week"),
)


def _normalize_report_key(report_key: str | None) -> str | None:
    normalized = (report_key or "").strip().lower()
    return normalized or None


def _report_category(report_key: str | None) -> str | None:
    normalized = _normalize_report_key(report_key)
    if not normalized:
        return None
    return _REPORT_CATEGORY_BY_KEY.get(normalized)


def _is_rate_metric_key(metric_key: str) -> bool:
    return "rate" in metric_key.lower()


def _is_currency_metric_key(metric_key: str) -> bool:
    key = metric_key.lower()
    return "charge" in key or "paid" in key or key.startswith("ar_") or "ar_balance" in key


def _title_case_from_key(key: str) -> str:
    return " ".join(part.capitalize() for part in key.split("_") if part)


def _format_metric_value(metric_key: str, value: float | None) -> str:
    if value is None:
        return "-"
    if _is_rate_metric_key(metric_key):
        ratio = value * 100 if value <= 1 else value
        return f"{ratio:.1f}%"
    if _is_currency_metric_key(metric_key):
        return f"${value:,.0f}"
    if abs(value - round(value)) < 0.0001:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def _rows_in_window(rows: list[AnalyticsQueryRow], start: dt.date, end: dt.date) -> list[AnalyticsQueryRow]:
    filtered: list[AnalyticsQueryRow] = []
    for row in rows:
        candidate: dt.date | None = None
        if row.kpi_date is not None:
            candidate = row.kpi_date
        elif row.as_of_ts is not None:
            candidate = row.as_of_ts.date()
        if candidate is None:
            continue
        if start <= candidate <= end:
            filtered.append(row)
    return filtered


def _aggregate(metric_key: str, rows: list[AnalyticsQueryRow]) -> float | None:
    values = [
        float(row.value_num)
        for row in rows
        if row.value_num is not None and not isinstance(row.value_num, bool)
    ]
    if not values:
        return None
    if _is_rate_metric_key(metric_key):
        return sum(values) / float(len(values))
    return sum(values)


def _latest(rows: list[AnalyticsQueryRow]) -> float | None:
    values = [
        float(row.value_num)
        for row in rows
        if row.value_num is not None and not isinstance(row.value_num, bool)
    ]
    if not values:
        return None
    return values[-1]


def _default_current_window(today: dt.date) -> tuple[dt.date, dt.date]:
    start = today - dt.timedelta(days=today.weekday())
    return start, today


def _baseline_window(current_start: dt.date, current_end: dt.date) -> tuple[dt.date, dt.date]:
    window_days = (current_end - current_start).days + 1
    baseline_end = current_start - dt.timedelta(days=1)
    baseline_start = baseline_end - dt.timedelta(days=window_days - 1)
    return baseline_start, baseline_end


def _select_metric_keys(
    *,
    prompt: str,
    report_key: str | None,
    allowed_metrics: list[AnalyticsMetricRead],
) -> list[str]:
    normalized_prompt = prompt.strip().lower()
    if not normalized_prompt:
        return []

    candidate_metrics = allowed_metrics
    report_category = _report_category(report_key)
    if report_category in _REPORT_CATEGORY_TO_METRIC_CATEGORIES:
        allowed_categories = _REPORT_CATEGORY_TO_METRIC_CATEGORIES[report_category]
        candidate_metrics = [row for row in allowed_metrics if (row.category or "").strip().lower() in allowed_categories]

    available_keys = {row.metric_key for row in candidate_metrics}

    selected: list[str] = []

    # Direct metric_key mention.
    for key in sorted(available_keys, key=len, reverse=True):
        if key.lower() in normalized_prompt:
            selected.append(key)

    # Keyword-to-metric mapping.
    for pattern, metric_key in _KEYWORD_METRIC_RULES:
        if pattern.search(normalized_prompt) and metric_key in available_keys:
            selected.append(metric_key)

    report_defaults = _DEFAULT_METRICS_BY_REPORT_KEY.get(_normalize_report_key(report_key) or "", [])
    defaults = [key for key in report_defaults if key in available_keys]

    deduped = list(dict.fromkeys([item.strip().lower() for item in selected if item.strip()]))
    if not deduped:
        deduped = defaults
    if not deduped:
        deduped = sorted(list(available_keys))[:6]

    return deduped[:8]


def _intent_from_prompt(prompt: str) -> str:
    lowered = prompt.strip().lower()
    if any(token in lowered for token in ["why", "root cause", "drivers"]):
        return "root_cause"
    if any(token in lowered for token in ["trend", "over time", "change", "week", "month"]):
        return "trend"
    if any(token in lowered for token in ["risk", "compliance", "audit", "unsigned"]):
        return "risk"
    if any(token in lowered for token in ["revenue", "denial", "ar", "paid", "payment", "charge"]):
        return "revenue"
    return "dashboard_question"


def _next_steps_for_metric(metric_key: str) -> list[str]:
    key = metric_key.lower()
    if "denial_rate" in key:
        return [
            "Review denied claims for trends by payer and service date; confirm top denial reasons.",
            "Validate eligibility and authorization checks for the cohort driving the change.",
        ]
    if key.startswith("ar_") or "ar_balance" in key:
        return [
            "Drill into A/R aging buckets and identify top balances over 30/60/90 days.",
            "Confirm submission cadence and investigate stalled claims with no recent payer activity.",
        ]
    if "unsigned" in key:
        return [
            "Route unsigned documentation to responsible staff and monitor SLA compliance (24h/72h).",
            "Slice by facility/program/provider to identify the backlog drivers and assign owners.",
        ]
    if "encounter" in key:
        return [
            "Review scheduling and staffing coverage for the largest swing days in the period.",
            "Slice by facility/program/provider to identify where throughput shifted.",
        ]
    if "attendance" in key or "no_show" in key:
        return [
            "Review reminder and outreach workflows for high no-show cohorts; confirm transportation/escalation steps.",
            "Slice by facility/program to identify operational bottlenecks affecting attendance.",
        ]
    if "active_clients" in key or "census" in key:
        return [
            "Validate admissions/discharges drivers behind census changes; review referral pipeline if needed.",
        ]
    return [
        "Validate metric movement by slicing facility/program/provider, then confirm an owner for follow-up actions.",
    ]


def _suggest_missing_metric_key(prompt: str) -> str:
    lowered = prompt.strip().lower()
    tokens = re.findall(r"[a-z0-9]+", lowered)[:6]
    if not tokens:
        return "new_metric_key"
    candidate = "_".join(tokens)
    candidate = re.sub(r"_{2,}", "_", candidate).strip("_")
    return (candidate[:80] or "new_metric_key").lower()


@router.post("/ai/query", response_model=AnalyticsAiQueryResponse)
def analytics_ai_query(
    payload: AnalyticsAiQueryRequest,
    request: Request,
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("analytics:view")),
) -> AnalyticsAiQueryResponse:
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="prompt is required")

    report_key = _normalize_report_key(payload.report_key)
    today = dt.datetime.now(dt.UTC).date()
    default_start, default_end = _default_current_window(today)

    filters = payload.filters or AnalyticsAiFilters()
    current_start = filters.start or default_start
    current_end = filters.end or default_end
    if current_start > current_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="filters.start cannot be after filters.end")

    baseline_start, baseline_end = _baseline_window(current_start, current_end)
    query_start = baseline_start
    query_end = current_end

    allowed_metrics = list_analytics_metrics(db=db, membership=membership, _=None)
    metrics_used = _select_metric_keys(prompt=prompt, report_key=report_key, allowed_metrics=allowed_metrics)

    filters_applied: dict = {
        "start": current_start.isoformat(),
        "end": current_end.isoformat(),
        "facility_id": (filters.facility_id or None),
        "program_id": (filters.program_id or None),
        "provider_id": (filters.provider_id or None),
        "payer_id": (filters.payer_id or None),
    }

    query_requests: list[dict] = []
    evidence: list[AnalyticsAiEvidenceMetric] = []

    if metrics_used:
        for metric_key in metrics_used:
            query_requests.append(
                {
                    "metric_key": metric_key,
                    "start": query_start.isoformat(),
                    "end": query_end.isoformat(),
                    "facility_id": filters.facility_id,
                    "program_id": filters.program_id,
                    "provider_id": filters.provider_id,
                    "payer_id": filters.payer_id,
                }
            )

            try:
                metric_payload = query_analytics_metric(
                    request=request,
                    metric_key=metric_key,
                    start=query_start,
                    end=query_end,
                    facility_id=filters.facility_id,
                    program_id=filters.program_id,
                    provider_id=filters.provider_id,
                    payer_id=filters.payer_id,
                    db=db,
                    membership=membership,
                    _=None,
                )

                current_rows = _rows_in_window(metric_payload.rows, current_start, current_end)
                baseline_rows = _rows_in_window(metric_payload.rows, baseline_start, baseline_end)

                is_snapshot = metric_payload.grain == _SNAPSHOT_GRAIN
                current_value = _latest(current_rows) if is_snapshot else _aggregate(metric_key, current_rows)
                baseline_value = _latest(baseline_rows) if is_snapshot else _aggregate(metric_key, baseline_rows)

                delta_value = None
                delta_pct = None
                if current_value is not None and baseline_value is not None:
                    delta_value = current_value - baseline_value
                    if baseline_value != 0:
                        delta_pct = (delta_value / abs(baseline_value)) * 100.0

                evidence.append(
                    AnalyticsAiEvidenceMetric(
                        metric_key=metric_key,
                        label=_title_case_from_key(metric_key),
                        grain=metric_payload.grain,
                        current_range_start=current_start,
                        current_range_end=current_end,
                        baseline_range_start=baseline_start,
                        baseline_range_end=baseline_end,
                        current_value=current_value,
                        baseline_value=baseline_value,
                        delta_value=delta_value,
                        delta_pct=delta_pct,
                        error=None,
                    )
                )
            except HTTPException:
                raise
            except Exception as exc:
                logger.exception("analytics.ai metric query failed metric_key=%s report_key=%s", metric_key, report_key)
                evidence.append(
                    AnalyticsAiEvidenceMetric(
                        metric_key=metric_key,
                        label=_title_case_from_key(metric_key),
                        grain="unknown",
                        current_range_start=current_start,
                        current_range_end=current_end,
                        baseline_range_start=baseline_start,
                        baseline_range_end=baseline_end,
                        current_value=None,
                        baseline_value=None,
                        delta_value=None,
                        delta_pct=None,
                        error=str(exc),
                    )
                )

    next_steps: list[str] = []
    for metric_key in metrics_used:
        for item in _next_steps_for_metric(metric_key):
            if item not in next_steps:
                next_steps.append(item)
            if len(next_steps) >= 6:
                break
        if len(next_steps) >= 6:
            break

    intent = _intent_from_prompt(prompt)
    rationale_parts: list[str] = []
    if report_key:
        rationale_parts.append(f"Report context: {report_key}")
        report_category = _report_category(report_key)
        if report_category:
            rationale_parts.append(f"Report category: {report_category}")
    if metrics_used:
        rationale_parts.append(f"Selected metrics: {', '.join(metrics_used)}")
    rationale_parts.append(f"Filters: {filters_applied}")
    rationale = "; ".join(rationale_parts)

    if not metrics_used:
        suggested_metric = _suggest_missing_metric_key(prompt)
        answer = (
            "I cannot answer that question with the currently registered analytics metrics.\n\n"
            f"Suggested backlog metric_key to add: `{suggested_metric}`.\n"
            "Once that metric is added to the analytics catalog and backed by a KPI table, EI can answer this."
        )
    else:
        lines: list[str] = []
        lines.append(
            f"Time window: {current_start.isoformat()} to {current_end.isoformat()} "
            f"(baseline: {baseline_start.isoformat()} to {baseline_end.isoformat()})."
        )
        for item in evidence:
            if item.error:
                lines.append(f"- {item.label}: unavailable ({item.error})")
                continue
            current_label = _format_metric_value(item.metric_key, item.current_value)
            baseline_label = _format_metric_value(item.metric_key, item.baseline_value)
            delta_pct = item.delta_pct
            delta_label = ""
            if isinstance(delta_pct, float):
                sign = "+" if delta_pct >= 0 else "-"
                delta_label = f" ({sign}{abs(delta_pct):.1f}% vs baseline)"
            lines.append(f"- {item.label}: {current_label} (baseline {baseline_label}){delta_label}")

        answer = "\n".join(lines)

    # Persist an audit record for full traceability (no row-level KPI data).
    tenant_id = _uuid_string_or_400(membership.organization_id, field_name="organization_id")
    audit_row = AnalyticsAiAuditLog(
        organization_id=tenant_id,
        membership_id=_uuid_string_or_400(membership.id, field_name="membership_id"),
        user_id=_uuid_string_or_400(membership.user_id, field_name="user_id"),
        report_key=report_key,
        conversation_id=str(uuid4()),
        message_id=str(uuid4()),
        user_prompt=prompt,
        intent=intent,
        rationale=rationale,
        metrics_used=metrics_used,
        filters_applied=filters_applied,
        query_requests=query_requests,
        query_responses_summary={
            # Ensure JSON-serializable payloads for Postgres JSONB / SQLite JSON.
            "evidence": [row.model_dump(mode="json", exclude_none=True) for row in evidence],
            "window": {
                "current_start": current_start.isoformat(),
                "current_end": current_end.isoformat(),
                "baseline_start": baseline_start.isoformat(),
                "baseline_end": baseline_end.isoformat(),
            },
        },
    )
    db.add(audit_row)
    db.commit()
    db.refresh(audit_row)

    log_event(
        db,
        action="analytics.ai_query",
        entity_type="analytics_ai",
        entity_id=audit_row.id,
        organization_id=tenant_id,
        actor=membership.user.email,
        metadata={
            "org_id": tenant_id,
            "user_id": membership.user_id,
            "membership_id": membership.id,
            "report_key": report_key,
            "intent": intent,
            "metrics_used": metrics_used,
            "filters_applied": filters_applied,
        },
    )

    return AnalyticsAiQueryResponse(
        answer=answer,
        metrics_used=metrics_used,
        filters_applied=filters_applied,
        next_step_tasks=next_steps,
        evidence=evidence,
    )


def _audit_log_read(row: AnalyticsAiAuditLog) -> AnalyticsAiAuditLogRead:
    return AnalyticsAiAuditLogRead(
        id=row.id,
        organization_id=row.organization_id,
        membership_id=row.membership_id,
        user_id=row.user_id,
        report_key=row.report_key,
        conversation_id=row.conversation_id,
        message_id=row.message_id,
        user_prompt=row.user_prompt,
        intent=row.intent,
        rationale=row.rationale,
        metrics_used=[str(item) for item in (row.metrics_used or [])],
        filters_applied=row.filters_applied or {},
        query_requests=[dict(item) for item in (row.query_requests or [])],
        query_responses_summary=row.query_responses_summary or {},
        created_at=row.created_at,
    )


@router.get("/ai/audit", response_model=list[AnalyticsAiAuditLogRead])
def list_analytics_ai_audit_logs(
    report_key: str | None = Query(default=None),
    since: dt.datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    conversation_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("analytics:view")),
) -> list[AnalyticsAiAuditLogRead]:
    tenant_id = _uuid_string_or_400(membership.organization_id, field_name="organization_id")
    query = select(AnalyticsAiAuditLog).where(AnalyticsAiAuditLog.organization_id == tenant_id)

    if report_key and report_key.strip():
        query = query.where(AnalyticsAiAuditLog.report_key == report_key.strip().lower())
    if since:
        query = query.where(AnalyticsAiAuditLog.created_at >= since)
    if conversation_id and conversation_id.strip():
        convo = _uuid_string_or_400(conversation_id.strip(), field_name="conversation_id")
        query = query.where(AnalyticsAiAuditLog.conversation_id == convo)

    rows = (
        db.execute(query.order_by(AnalyticsAiAuditLog.created_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [_audit_log_read(row) for row in rows]
