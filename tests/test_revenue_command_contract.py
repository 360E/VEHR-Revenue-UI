from __future__ import annotations

from uuid import uuid4
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.rbac import ROLE_ADMIN
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.audit_event import AuditEvent
from app.db.models.organization import Organization
from app.db.models.organization_membership import OrganizationMembership
from app.db.models.user import User
from app.db.session import get_db
from app.main import app

DUMMY_HASH = "test-hash-not-used"


def _setup_db(tmp_path):
  database_file = tmp_path / "revenue_command.sqlite"
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
  return engine, TestingSessionLocal


def _auth_header(token: str) -> dict[str, str]:
  return {"Authorization": f"Bearer {token}"}


def _create_membership(db):
  org = Organization(name="Revenue Command Org")
  db.add(org)
  db.flush()

  user = User(
    email="revenue-command@example.com",
    full_name="Revenue Command Tester",
    hashed_password=DUMMY_HASH,
    is_active=True,
  )
  db.add(user)
  db.flush()

  db.add(
    OrganizationMembership(
      organization_id=org.id,
      user_id=user.id,
      role=ROLE_ADMIN,
    )
  )
  db.commit()
  db.refresh(org)
  db.refresh(user)
  return org, user


def test_revenue_command_contract(tmp_path) -> None:
  engine, TestingSessionLocal = _setup_db(tmp_path)
  try:
    with TestingSessionLocal() as db:
      org, user = _create_membership(db)
      token = create_access_token({"sub": user.id, "org_id": org.id})

    request_body = {
      "job_id": str(uuid4()),
      "date_range": {"start": "2024-12-01", "end": "2024-12-31"},
      "payer_id": str(uuid4()),
    }

    with TestClient(app) as client:
      response = client.post(
        "/api/v1/ai/revenue-command",
        headers=_auth_header(token),
        json=request_body,
      )

    assert response.status_code == 200
    body = response.json()
    expected_keys = {
      "summary",
      "financial_impact",
      "30_day_execution_plan",
      "90_day_structural_moves",
      "top_risks",
      "payer_escalation_targets",
      "staffing_recommendations",
      "monitoring_metrics",
      "data_used",
      "assumptions",
      "confidence",
    }
    assert set(body.keys()) == expected_keys

    for money_field in ("total_exposure", "expected_recovery", "short_term_cash_opportunity"):
      assert isinstance(body["financial_impact"][money_field], str)

    assert isinstance(body["30_day_execution_plan"], list)
    assert body["30_day_execution_plan"]
    first_item = body["30_day_execution_plan"][0]
    assert set(first_item.keys()) == {"initiative", "expected_impact", "effort_level", "owner"}
    assert all(isinstance(first_item[key], str) for key in first_item)

    assert isinstance(body["confidence"], (float, int))
    assert 0 <= body["confidence"] <= 1
    assert isinstance(body["90_day_structural_moves"], list)
    assert isinstance(body["top_risks"], list)
    assert isinstance(body["payer_escalation_targets"], list)
    assert isinstance(body["staffing_recommendations"], list)
    assert isinstance(body["monitoring_metrics"], list)
    assert isinstance(body["data_used"], list)
    assert isinstance(body["assumptions"], list)
  finally:
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_revenue_command_rejects_malformed_response(monkeypatch, tmp_path) -> None:
  from app.api.v1.endpoints import revenue_command as revenue_command_module

  engine, TestingSessionLocal = _setup_db(tmp_path)
  try:
    with TestingSessionLocal() as db:
      org, user = _create_membership(db)
      token = create_access_token({"sub": user.id, "org_id": org.id})
      baseline_audits = db.execute(select(AuditEvent)).all()

    malformed_response = {
      "summary": "bad",
      "financial_impact": {
        "total_exposure": "1000",
        "expected_recovery": "500",
        "short_term_cash_opportunity": "100",
      },
      "30_day_execution_plan": [],
      "90_day_structural_moves": [],
      "top_risks": [],
      "payer_escalation_targets": [],
      "staffing_recommendations": [],
      "monitoring_metrics": [],
      "data_used": [],
      "assumptions": [],
      "confidence": 0.5,
      "unexpected": "extra",
    }

    def _bad_plan(*_args, **_kwargs):
      return malformed_response

    monkeypatch.setattr(revenue_command_module, "_build_revenue_command_plan", _bad_plan)

    with TestClient(app) as client:
      response = client.post(
        "/api/v1/ai/revenue-command",
        headers=_auth_header(token),
        json={},
      )

    assert response.status_code in {500, 422}

    with TestingSessionLocal() as db:
      assert len(db.execute(select(AuditEvent)).all()) == len(baseline_audits)
      assert db.execute(select(Organization)).scalar_one().name == "Revenue Command Org"
  finally:
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
