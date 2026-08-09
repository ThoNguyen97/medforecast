"""
Tests for Procurement API endpoints (task 8.2)

Covers:
- GET    /api/v1/procurement              (list with filters)
- POST   /api/v1/procurement/generate    (auto-generate from alerts)
- GET    /api/v1/procurement/export      (PDF and Excel export)
- GET    /api/v1/procurement/{id}        (get by ID)
- PUT    /api/v1/procurement/{id}        (update)
- DELETE /api/v1/procurement/{id}        (delete)
- POST   /api/v1/procurement/{id}/approve (approve)
- Schema validation
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models.medical_supply import MedicalSupply
from app.models.procurement_plan import ProcurementPlan
from app.models.user import User
from app.core.security import get_password_hash, create_access_token
from app.procurement.procurement_planner import ProcurementPlanItem


# ── Test database setup ────────────────────────────────────────────────────────

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_procurement.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh isolated database for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """TestClient wired to the test database."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    user = User(
        username="testadmin",
        email="admin@test.com",
        password_hash=get_password_hash("testpassword"),
        full_name="Test Admin",
        role="Administrator",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(data={"sub": test_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_supply(db_session) -> MedicalSupply:
    supply = MedicalSupply(
        name="Surgical Masks",
        category="PPE",
        unit="box",
        unit_price=5.0,
        minimum_order_quantity=10,
        lead_time_days=3,
        storage_capacity=1000,
    )
    db_session.add(supply)
    db_session.commit()
    db_session.refresh(supply)
    return supply


@pytest.fixture
def sample_plan(db_session, sample_supply, test_user) -> ProcurementPlan:
    plan = ProcurementPlan(
        supply_id=sample_supply.id,
        order_quantity=100,
        order_date=date.today(),
        expected_delivery_date=date.today() + timedelta(days=3),
        estimated_cost=Decimal("500.00"),
        priority="critical",
        status="pending",
        notes="Test plan",
        created_by=test_user.id,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


# ── List Procurement Plans ─────────────────────────────────────────────────────

class TestListProcurementPlans:
    def test_returns_empty_list_initially(self, client, auth_headers):
        resp = client.get("/api/v1/procurement", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_plans_after_seeding(self, client, auth_headers, sample_plan):
        resp = client.get("/api/v1/procurement", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == sample_plan.id
        assert data[0]["supply_name"] == "Surgical Masks"

    def test_filter_by_status_pending(self, client, auth_headers, sample_plan):
        resp = client.get("/api/v1/procurement?status=pending", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_by_status_approved_returns_empty(self, client, auth_headers, sample_plan):
        resp = client.get("/api/v1/procurement?status=approved", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_filter_by_priority_critical(self, client, auth_headers, sample_plan):
        resp = client.get("/api/v1/procurement?priority=critical", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_by_supply_id(self, client, auth_headers, sample_plan, sample_supply):
        resp = client.get(
            f"/api/v1/procurement?supply_id={sample_supply.id}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_requires_authentication(self, client):
        resp = client.get("/api/v1/procurement")
        assert resp.status_code == 401


# ── Get Plan By ID ─────────────────────────────────────────────────────────────

class TestGetProcurementPlanById:
    def test_returns_plan_for_valid_id(self, client, auth_headers, sample_plan):
        resp = client.get(f"/api/v1/procurement/{sample_plan.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sample_plan.id
        assert data["supply_name"] == "Surgical Masks"
        assert data["order_quantity"] == 100
        assert data["priority"] == "critical"
        assert data["status"] == "pending"

    def test_returns_404_for_missing_plan(self, client, auth_headers):
        resp = client.get("/api/v1/procurement/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_requires_authentication(self, client, sample_plan):
        resp = client.get(f"/api/v1/procurement/{sample_plan.id}")
        assert resp.status_code == 401


# ── Update Plan ────────────────────────────────────────────────────────────────

class TestUpdateProcurementPlan:
    def test_update_order_quantity(self, client, auth_headers, sample_plan):
        resp = client.put(
            f"/api/v1/procurement/{sample_plan.id}",
            json={"order_quantity": 250},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["order_quantity"] == 250

    def test_update_notes(self, client, auth_headers, sample_plan):
        resp = client.put(
            f"/api/v1/procurement/{sample_plan.id}",
            json={"notes": "Updated notes"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Updated notes"

    def test_cannot_update_approved_plan(
        self, client, auth_headers, db_session, sample_plan
    ):
        # First approve the plan
        sample_plan.status = "approved"
        db_session.commit()

        resp = client.put(
            f"/api/v1/procurement/{sample_plan.id}",
            json={"order_quantity": 999},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "approved" in resp.json()["detail"].lower()

    def test_returns_404_for_missing_plan(self, client, auth_headers):
        resp = client.put(
            "/api/v1/procurement/99999",
            json={"notes": "Does not exist"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ── Delete Plan ────────────────────────────────────────────────────────────────

class TestDeleteProcurementPlan:
    def test_delete_pending_plan(self, client, auth_headers, db_session, sample_plan):
        plan_id = sample_plan.id
        resp = client.delete(f"/api/v1/procurement/{plan_id}", headers=auth_headers)
        assert resp.status_code == 204
        # Verify it's gone
        assert db_session.get(ProcurementPlan, plan_id) is None

    def test_cannot_delete_approved_plan(
        self, client, auth_headers, db_session, sample_plan
    ):
        sample_plan.status = "approved"
        db_session.commit()

        resp = client.delete(
            f"/api/v1/procurement/{sample_plan.id}", headers=auth_headers
        )
        assert resp.status_code == 400
        assert "approved" in resp.json()["detail"].lower()

    def test_returns_404_for_missing_plan(self, client, auth_headers):
        resp = client.delete("/api/v1/procurement/99999", headers=auth_headers)
        assert resp.status_code == 404


# ── Approve Plan ───────────────────────────────────────────────────────────────

class TestApproveProcurementPlan:
    def test_approve_pending_plan_sets_status(
        self, client, auth_headers, db_session, sample_plan
    ):
        resp = client.post(
            f"/api/v1/procurement/{sample_plan.id}/approve", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"

        # Verify in DB
        db_session.refresh(sample_plan)
        assert sample_plan.status == "approved"

    def test_cannot_approve_already_approved_plan(
        self, client, auth_headers, db_session, sample_plan
    ):
        sample_plan.status = "approved"
        db_session.commit()

        resp = client.post(
            f"/api/v1/procurement/{sample_plan.id}/approve", headers=auth_headers
        )
        assert resp.status_code == 400
        assert "already approved" in resp.json()["detail"].lower()

    def test_returns_404_for_missing_plan(self, client, auth_headers):
        resp = client.post("/api/v1/procurement/99999/approve", headers=auth_headers)
        assert resp.status_code == 404


# ── Generate Plans ─────────────────────────────────────────────────────────────

class TestGenerateProcurementPlans:
    def test_generate_with_no_requirements_returns_empty(self, client, auth_headers):
        """With no supply requirements in DB, generate returns no plans."""
        resp = client.post(
            "/api/v1/procurement/generate",
            json={"forecast_days": 30},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["plans_generated"] == 0
        assert data["plans"] == []

    def test_generate_forecast_days_too_small_returns_422(self, client, auth_headers):
        resp = client.post(
            "/api/v1/procurement/generate",
            json={"forecast_days": 3},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_generate_forecast_days_too_large_returns_422(self, client, auth_headers):
        resp = client.post(
            "/api/v1/procurement/generate",
            json={"forecast_days": 200},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_generate_default_forecast_days(self, client, auth_headers):
        """Default forecast_days=30 is accepted."""
        resp = client.post(
            "/api/v1/procurement/generate",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 201

    def test_generate_requires_authentication(self, client):
        resp = client.post("/api/v1/procurement/generate", json={"forecast_days": 30})
        assert resp.status_code == 401


# ── Export ─────────────────────────────────────────────────────────────────────

class TestExportProcurementPlans:
    def test_export_excel_returns_xlsx_content_type(
        self, client, auth_headers, sample_plan
    ):
        resp = client.get(
            "/api/v1/procurement/export?format=excel", headers=auth_headers
        )
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers["content-type"]
        assert len(resp.content) > 0

    def test_export_pdf_returns_pdf_content_type(
        self, client, auth_headers, sample_plan
    ):
        resp = client.get(
            "/api/v1/procurement/export?format=pdf", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert len(resp.content) > 0

    def test_export_invalid_format_rejected(self, client, auth_headers):
        resp = client.get(
            "/api/v1/procurement/export?format=csv", headers=auth_headers
        )
        assert resp.status_code == 422

    def test_export_excel_with_no_plans(self, client, auth_headers):
        """Export with empty plans list still returns a valid Excel file."""
        resp = client.get(
            "/api/v1/procurement/export?format=excel", headers=auth_headers
        )
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers["content-type"]

    def test_export_pdf_with_no_plans(self, client, auth_headers):
        """Export with empty plans list still returns a valid PDF file."""
        resp = client.get(
            "/api/v1/procurement/export?format=pdf", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

    def test_export_default_format_is_excel(self, client, auth_headers, sample_plan):
        """Default format when not specified should be excel."""
        resp = client.get("/api/v1/procurement/export", headers=auth_headers)
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers["content-type"]

    def test_export_requires_authentication(self, client):
        resp = client.get("/api/v1/procurement/export?format=excel")
        assert resp.status_code == 401


# ── Schema validation ──────────────────────────────────────────────────────────

class TestProcurementSchemas:
    def test_procurement_plan_response_includes_supply_name(self):
        from app.schemas.base import ProcurementPlanResponse

        plan = ProcurementPlanResponse(
            id=1,
            supply_id=1,
            supply_name="Surgical Masks",
            order_quantity=100,
            order_date=date.today(),
            status="pending",
            created_at=datetime.now(),
        )
        assert plan.supply_name == "Surgical Masks"

    def test_procurement_plan_update_all_optional(self):
        from app.schemas.base import ProcurementPlanUpdate

        update = ProcurementPlanUpdate()
        assert update.order_quantity is None
        assert update.notes is None

    def test_procurement_generate_request_defaults(self):
        from app.schemas.base import ProcurementGenerateRequest

        req = ProcurementGenerateRequest()
        assert req.forecast_days == 30

    def test_procurement_generate_request_validation_below_min(self):
        from pydantic import ValidationError
        from app.schemas.base import ProcurementGenerateRequest

        with pytest.raises(ValidationError):
            ProcurementGenerateRequest(forecast_days=5)

    def test_procurement_generate_request_validation_above_max(self):
        from pydantic import ValidationError
        from app.schemas.base import ProcurementGenerateRequest

        with pytest.raises(ValidationError):
            ProcurementGenerateRequest(forecast_days=100)
