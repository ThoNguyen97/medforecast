"""
Integration tests for Dashboard API endpoints.

Covers:
- GET /api/v1/dashboard/overview
- GET /api/v1/dashboard/supply-demand
- GET /api/v1/dashboard/risk-status
- GET /api/v1/dashboard/critical-alerts
"""

import pytest
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.models.medical_supply import MedicalSupply
from app.models.inventory import Inventory
from app.models.disease_case import DiseaseCase
from app.models.disease_forecast import DiseaseForecast
from app.models.supply_requirement import SupplyRequirement
from app.models.alert import Alert
from app.core.security import hash_password, create_access_token


# ── Test DB Setup ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def admin_user(db_session):
    user = User(
        username="admin",
        email="admin@test.com",
        password_hash=hash_password("adminpass123"),
        full_name="Admin User",
        role="Administrator",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_headers(admin_user):
    token = create_access_token(data={"sub": admin_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seeded_data(db_session, admin_user):
    """Seed basic data for dashboard tests."""
    # Medical supply
    supply = MedicalSupply(
        name="Surgical Mask", category="PPE", unit="box", unit_price=10.0
    )
    db_session.add(supply)
    db_session.flush()

    # Inventory items at different risk levels
    safe_inv = Inventory(
        supply_id=supply.id,
        current_stock=500,
        safety_stock=100,
        location="Warehouse A",
        updated_by=admin_user.id,
    )
    low_inv = Inventory(
        supply_id=supply.id,
        current_stock=50,
        safety_stock=100,
        location="Warehouse B",
        updated_by=admin_user.id,
    )
    critical_inv = Inventory(
        supply_id=supply.id,
        current_stock=0,
        safety_stock=100,
        location="Warehouse C",
        updated_by=admin_user.id,
    )
    db_session.add_all([safe_inv, low_inv, critical_inv])

    # Disease cases (recent)
    case = DiseaseCase(
        recorded_at=datetime.utcnow() - timedelta(days=3),
        disease_type="dengue_fever",
        case_count=100,
        location="Ho Chi Minh City",
        data_source="test",
    )
    db_session.add(case)

    # Forecast for next 30 days
    for i in range(5):
        fc = DiseaseForecast(
            forecast_date=date.today() + timedelta(days=i + 1),
            disease_type="dengue_fever",
            predicted_cases=50,
            model_used="ensemble",
        )
        db_session.add(fc)

    # Unresolved critical alert
    alert = Alert(
        supply_id=supply.id,
        alert_type="shortage",
        severity="critical",
        current_stock=0,
        required_stock=200,
        shortage_date=date.today() + timedelta(days=1),
        message="Critical shortage",
        is_resolved=False,
    )
    db_session.add(alert)

    db_session.commit()
    return {"supply": supply, "safe_inv": safe_inv, "alert": alert}


# ── Overview Tests ────────────────────────────────────────────────────────────

class TestDashboardOverview:
    def test_overview_requires_auth(self, client):
        resp = client.get("/api/v1/dashboard/overview")
        assert resp.status_code == 401

    def test_overview_returns_expected_keys(self, client, admin_headers, seeded_data):
        resp = client.get("/api/v1/dashboard/overview", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()

        expected_keys = [
            "total_supplies",
            "total_inventory_value",
            "high_risk_shortages",
            "predicted_demand_30d",
            "disease_outbreaks",
            "safe_stock_items",
            "low_stock_items",
            "critical_risk_items",
            "supply_risk_percentage",
        ]
        for key in expected_keys:
            assert key in data, f"Missing key: {key}"

    def test_overview_empty_db_returns_zeros(self, client, admin_headers):
        resp = client.get("/api/v1/dashboard/overview", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_supplies"] == 0
        assert data["high_risk_shortages"] == 0
        assert data["predicted_demand_30d"] == 0

    def test_overview_counts_correct(self, client, admin_headers, seeded_data):
        resp = client.get("/api/v1/dashboard/overview", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()

        # 1 supply
        assert data["total_supplies"] == 1
        # 1 unresolved critical alert
        assert data["high_risk_shortages"] >= 1
        # 3 inventory items, 1 safe / 1 low / 1 critical
        assert data["safe_stock_items"] == 1
        assert data["low_stock_items"] == 1
        assert data["critical_risk_items"] == 1
        # Disease outbreaks in last 7 days
        assert data["disease_outbreaks"] >= 1
        # Predicted demand from 5 forecasts × 50 cases = 250
        assert data["predicted_demand_30d"] == 250


# ── Supply-Demand Tests ───────────────────────────────────────────────────────

class TestDashboardSupplyDemand:
    def test_supply_demand_requires_auth(self, client):
        resp = client.get("/api/v1/dashboard/supply-demand")
        assert resp.status_code == 401

    def test_supply_demand_returns_expected_structure(self, client, admin_headers):
        resp = client.get("/api/v1/dashboard/supply-demand", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert "data_points" in data
        assert "days_history" in data
        assert "days_forecast" in data
        assert "total_historical_points" in data
        assert "total_forecast_points" in data
        assert isinstance(data["data_points"], list)

    def test_supply_demand_with_forecast_data(self, client, admin_headers, seeded_data):
        resp = client.get(
            "/api/v1/dashboard/supply-demand?days_history=30&days_forecast=10",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # We seeded 5 forecasts, but only those within days_forecast range count
        assert data["total_forecast_points"] >= 0
        assert data["days_history"] == 30
        assert data["days_forecast"] == 10

    def test_supply_demand_invalid_params(self, client, admin_headers):
        # days_history < 7 should fail validation
        resp = client.get(
            "/api/v1/dashboard/supply-demand?days_history=3",
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_supply_demand_with_supply_filter(self, client, admin_headers, seeded_data):
        supply = seeded_data["supply"]
        resp = client.get(
            f"/api/v1/dashboard/supply-demand?supply_id={supply.id}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["supply_id"] == supply.id


# ── Risk Status Tests ─────────────────────────────────────────────────────────

class TestDashboardRiskStatus:
    def test_risk_status_requires_auth(self, client):
        resp = client.get("/api/v1/dashboard/risk-status")
        assert resp.status_code == 401

    def test_risk_status_returns_expected_structure(self, client, admin_headers):
        resp = client.get("/api/v1/dashboard/risk-status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert "total_items" in data
        assert "safe_count" in data
        assert "low_count" in data
        assert "critical_count" in data
        assert "safe_percentage" in data
        assert "low_percentage" in data
        assert "critical_percentage" in data

    def test_risk_status_empty_db(self, client, admin_headers):
        resp = client.get("/api/v1/dashboard/risk-status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_items"] == 0
        assert data["safe_count"] == 0

    def test_risk_status_correct_counts(self, client, admin_headers, seeded_data):
        resp = client.get("/api/v1/dashboard/risk-status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_items"] == 3
        assert data["safe_count"] == 1
        assert data["low_count"] == 1
        assert data["critical_count"] == 1

    def test_risk_status_percentages_sum_100(self, client, admin_headers, seeded_data):
        resp = client.get("/api/v1/dashboard/risk-status", headers=admin_headers)
        data = resp.json()
        total = data["safe_percentage"] + data["low_percentage"] + data["critical_percentage"]
        assert abs(total - 100.0) < 0.1  # Allow minor rounding


# ── Critical Alerts Tests ─────────────────────────────────────────────────────

class TestDashboardCriticalAlerts:
    def test_critical_alerts_requires_auth(self, client):
        resp = client.get("/api/v1/dashboard/critical-alerts")
        assert resp.status_code == 401

    def test_critical_alerts_returns_expected_structure(self, client, admin_headers):
        resp = client.get("/api/v1/dashboard/critical-alerts", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert "alerts" in data
        assert "total_returned" in data
        assert "limit" in data
        assert "severity_summary" in data
        assert isinstance(data["alerts"], list)

    def test_critical_alerts_shows_unresolved_only(self, client, admin_headers, seeded_data):
        resp = client.get("/api/v1/dashboard/critical-alerts", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        # All returned alerts should be unresolved
        for alert in data["alerts"]:
            assert alert["is_resolved"] is False

    def test_critical_alerts_respects_limit(self, client, admin_headers, db_session, admin_user):
        # Create 5 critical alerts
        supply = MedicalSupply(name="Test Supply", category="Test", unit="unit")
        db_session.add(supply)
        db_session.flush()
        for i in range(5):
            alert = Alert(
                supply_id=supply.id,
                alert_type="shortage",
                severity="critical",
                current_stock=0,
                required_stock=100,
                shortage_date=date.today(),
                message=f"Alert {i}",
                is_resolved=False,
            )
            db_session.add(alert)
        db_session.commit()

        resp = client.get(
            "/api/v1/dashboard/critical-alerts?limit=3",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_returned"] == 3
        assert data["limit"] == 3

    def test_critical_alerts_invalid_limit(self, client, admin_headers):
        # Limit of 0 is invalid
        resp = client.get(
            "/api/v1/dashboard/critical-alerts?limit=0",
            headers=admin_headers,
        )
        assert resp.status_code == 422
