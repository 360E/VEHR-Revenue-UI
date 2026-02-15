from __future__ import annotations

import datetime as dt
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.rbac import ROLE_ADMIN
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.analytics_ai_audit_log import AnalyticsAiAuditLog
from app.db.models.analytics_metric import AnalyticsMetric
from app.db.models.organization import Organization
from app.db.models.organization_membership import OrganizationMembership
from app.db.models.rpt_kpi_daily import RptKpiDaily
from app.db.models.user import User
from app.db.session import get_db
from app.main import app

DUMMY_HASH = "test-hash-not-used"


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_user_membership(db, *, organization_id: str, email: str, role: str) -> User:
    user = User(
        email=email,
        full_name=email.split("@", 1)[0],
        hashed_password=DUMMY_HASH,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        OrganizationMembership(
            organization_id=organization_id,
            user_id=user.id,
            role=role,
        )
    )
    db.flush()
    return user


def test_analytics_ai_routes_are_present_in_openapi() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    payload = response.json()
    assert "/api/v1/analytics/ai/query" in payload["paths"]
    assert "/api/v1/analytics/ai/audit" in payload["paths"]


def test_analytics_ai_query_writes_audit_and_is_tenant_scoped(tmp_path) -> None:
    database_file = tmp_path / "analytics_ai.sqlite"
    engine = create_engine(
        f"sqlite:///{database_file}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.db import models as _models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        current_start = dt.date(2026, 1, 8)
        current_end = dt.date(2026, 1, 10)
        baseline_start = dt.date(2026, 1, 5)
        baseline_end = dt.date(2026, 1, 7)

        with TestingSessionLocal() as db:
            org1 = Organization(name="AI Org 1")
            org2 = Organization(name="AI Org 2")
            db.add_all([org1, org2])
            db.flush()

            user1 = _create_user_membership(db, organization_id=org1.id, email="ai-admin1@example.com", role=ROLE_ADMIN)
            user2 = _create_user_membership(db, organization_id=org2.id, email="ai-admin2@example.com", role=ROLE_ADMIN)

            metric = AnalyticsMetric(
                metric_key="encounters_week",
                description="Encounter volume for the week.",
                category="operations",
                grain="daily",
                backing_table="rpt_kpi_daily",
                allowed_roles=["admin"],
                created_at=dt.datetime.now(dt.UTC),
                updated_at=dt.datetime.now(dt.UTC),
            )
            db.add(metric)

            for day in range((baseline_end - baseline_start).days + 1):
                date_value = baseline_start + dt.timedelta(days=day)
                db.add(
                    RptKpiDaily(
                        tenant_id=org1.id,
                        kpi_date=date_value,
                        metric_key="encounters_week",
                        value_num=Decimal("5"),
                        value_json=None,
                    )
                )
            for day in range((current_end - current_start).days + 1):
                date_value = current_start + dt.timedelta(days=day)
                db.add(
                    RptKpiDaily(
                        tenant_id=org1.id,
                        kpi_date=date_value,
                        metric_key="encounters_week",
                        value_num=Decimal("10"),
                        value_json=None,
                    )
                )

            db.commit()

            token1 = create_access_token({"sub": user1.id, "org_id": org1.id})
            token2 = create_access_token({"sub": user2.id, "org_id": org2.id})

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/analytics/ai/query",
                headers=_auth_header(token1),
                json={
                    "prompt": "How did encounters change?",
                    "report_key": "executive_overview",
                    "filters": {
                        "start": current_start.isoformat(),
                        "end": current_end.isoformat(),
                    },
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert "encounters_week" in body["metrics_used"]
        assert body["filters_applied"]["start"] == current_start.isoformat()
        assert body["filters_applied"]["end"] == current_end.isoformat()
        assert isinstance(body["next_step_tasks"], list)
        assert isinstance(body["evidence"], list)

        with TestingSessionLocal() as db:
            row = db.execute(
                select(AnalyticsAiAuditLog).where(AnalyticsAiAuditLog.organization_id == org1.id)
            ).scalar_one_or_none()
            assert row is not None
            assert row.report_key == "executive_overview"
            assert "encounters_week" in (row.metrics_used or [])
            summary = row.query_responses_summary or {}
            assert "rows" not in summary

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/analytics/ai/audit?limit=50",
                headers=_auth_header(token1),
            )
        assert response.status_code == 200
        audit_rows = response.json()
        assert len(audit_rows) == 1
        assert audit_rows[0]["organization_id"] == org1.id

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/analytics/ai/audit?limit=50",
                headers=_auth_header(token2),
            )
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

