"""
Integration tests for Reports API endpoints.

Covers:
- GET  /api/v1/reports/consumption
- GET  /api/v1/reports/forecast-accuracy
- GET  /api/v1/reports/inventory-turnover
- POST /api/v1/reports/export
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
from app.models.disease_forecast import DiseaseForecast
from app.models.supply_requirement import SupplyRequirement
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
def seeded_report_data(db_session, admin_user):
    """Seed data for reports."""
    supply = MedicalSupply(
        name="Surgical Mask", category="PPE", unit="box", unit_price=10.0
    )
    supply2 = MedicalSupply(
        name="Latex Gloves", category="PPE", unit="box", unit_price=5.0
    )
    db_session.add_all([supply, supply2])
    db_session.flush()

    # Inventory
    inv = Inventory(
        supply_id=supply.id,
        current_stock=500,
        safety_stock=100,
        location="Warehouse A",
        updated_by=admin_user.id,
    )
    db_session.add(inv)

    # Supply requirements (last 30 days)
    today = date.today()
    for i in range(5):
        req = SupplyRequirement(
            forecast_id=None,
            supply_id=supply.id,
            required_quantity=100,
            requirement_date=today - timedelta(days=i),
            disease_type="dengue_fever",
        )
        db_session.add(req)

    # Forecasts with accuracy metrics
    for i in range(3):
        fc = DiseaseForecast(
            forecast_date=today - timedelta(days=i),
            disease_type="dengue_fever",
            predicted_cases=100,
            model_used="ensemble",
            model_accuracy_mae=5.2,
            model_accuracy_rmse=7.8,
            model_accuracy_mape=4.5,
        )
        db_session.add(fc)

    db_session.commit()
    return {"supply": supply, "supply2": supply2}


# ── Consumption Report Tests ──────────────────────────────────────────────────

class TestConsumptionReport:
    def test_consumption_requires_auth(self, client):
        resp = client.get("/api/v1/reports/consumption")
        assert resp.status_code == 401

    def test_consumption_returns_expected_structure(self, client, admin_headers):
        resp = client.get("/api/v1/reports/consumption", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["report_type"] == "consumption"
        assert "period" in data
        assert "summary" in data
        assert "categories" in data
        assert "generated_at" in data

    def test_consumption_empty_returns_empty_categories(self, client, admin_headers):
        resp = client.get("/api/v1/reports/consumption", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["categories"] == []
        assert data["summary"]["total_required_across_all_categories"] == 0

    def test_consumption_with_data(self, client, admin_headers, seeded_report_data):
        resp = client.get("/api/v1/reports/consumption", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["categories"]) > 0
        # PPE category should be present
        ppe_cat = next((c for c in data["categories"] if c["category"] == "PPE"), None)
        assert ppe_cat is not None
        assert ppe_cat["total_required"] == 500  # 5 requirements × 100 each

    def test_consumption_filter_by_category(self, client, admin_headers, seeded_report_data):
        resp = client.get(
            "/api/v1/reports/consumption?category=PPE",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for cat in data["categories"]:
            assert cat["category"] == "PPE"

    def test_consumption_filter_by_date_range(self, client, admin_headers, seeded_report_data):
        today = date.today()
        resp = client.get(
            f"/api/v1/reports/consumption?start_date={today - timedelta(days=2)}&end_date={today}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Only 3 days of data should be included
        assert data["period"]["start_date"] == str(today - timedelta(days=2))
        assert data["period"]["end_date"] == str(today)


# ── Forecast Accuracy Report Tests ───────────────────────────────────────────

class TestForecastAccuracyReport:
    def test_accuracy_requires_auth(self, client):
        resp = client.get("/api/v1/reports/forecast-accuracy")
        assert resp.status_code == 401

    def test_accuracy_returns_expected_structure(self, client, admin_headers):
        resp = client.get("/api/v1/reports/forecast-accuracy", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["report_type"] == "forecast-accuracy"
        assert "period" in data
        assert "summary" in data
        assert "model_performance" in data
        assert "time_series" in data

    def test_accuracy_empty_returns_zero_forecasts(self, client, admin_headers):
        resp = client.get("/api/v1/reports/forecast-accuracy", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_forecasts"] == 0

    def test_accuracy_with_forecast_data(self, client, admin_headers, seeded_report_data):
        resp = client.get("/api/v1/reports/forecast-accuracy", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        # We seeded 3 forecasts but they might be outside the default 30-day window
        # Adjust date range to capture them
        today = date.today()
        resp = client.get(
            f"/api/v1/reports/forecast-accuracy?start_date={today - timedelta(days=10)}&end_date={today}",
            headers=admin_headers,
        )
        data = resp.json()
        assert data["summary"]["total_forecasts"] == 3
        assert len(data["model_performance"]) > 0

    def test_accuracy_filter_by_disease_type(self, client, admin_headers, seeded_report_data):
        today = date.today()
        resp = client.get(
            f"/api/v1/reports/forecast-accuracy?start_date={today - timedelta(days=10)}"
            f"&end_date={today}&disease_type=dengue_fever",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for ts in data["time_series"]:
            assert ts["disease_type"] == "dengue_fever"

    def test_accuracy_filter_by_model(self, client, admin_headers, seeded_report_data):
        today = date.today()
        resp = client.get(
            f"/api/v1/reports/forecast-accuracy?start_date={today - timedelta(days=10)}"
            f"&end_date={today}&model_used=ensemble",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for ts in data["time_series"]:
            assert ts["model"] == "ensemble"


# ── Inventory Turnover Report Tests ──────────────────────────────────────────

class TestInventoryTurnoverReport:
    def test_turnover_requires_auth(self, client):
        resp = client.get("/api/v1/reports/inventory-turnover")
        assert resp.status_code == 401

    def test_turnover_returns_expected_structure(self, client, admin_headers):
        resp = client.get("/api/v1/reports/inventory-turnover", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["report_type"] == "inventory-turnover"
        assert "period" in data
        assert "summary" in data
        assert "items" in data

    def test_turnover_empty_returns_no_items(self, client, admin_headers):
        resp = client.get("/api/v1/reports/inventory-turnover", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_items"] == 0
        assert data["items"] == []

    def test_turnover_with_inventory_data(self, client, admin_headers, seeded_report_data):
        resp = client.get("/api/v1/reports/inventory-turnover", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_items"] >= 1
        # Each item should have expected fields
        for item in data["items"]:
            assert "supply_name" in item
            assert "current_stock" in item
            assert "turnover_rate" in item

    def test_turnover_filter_by_category(self, client, admin_headers, seeded_report_data):
        resp = client.get(
            "/api/v1/reports/inventory-turnover?category=PPE",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["category"] == "PPE"


# ── Export Report Tests ───────────────────────────────────────────────────────

class TestExportReport:
    def test_export_requires_auth(self, client):
        resp = client.post(
            "/api/v1/reports/export",
            json={"report_type": "consumption"},
        )
        assert resp.status_code == 401

    def test_export_consumption_returns_pdf(self, client, admin_headers):
        resp = client.post(
            "/api/v1/reports/export",
            json={"report_type": "consumption"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers["content-type"]
        assert len(resp.content) > 0

    def test_export_forecast_accuracy_returns_pdf(self, client, admin_headers):
        resp = client.post(
            "/api/v1/reports/export",
            json={"report_type": "forecast-accuracy"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers["content-type"]

    def test_export_inventory_turnover_returns_pdf(self, client, admin_headers):
        resp = client.post(
            "/api/v1/reports/export",
            json={"report_type": "inventory-turnover"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers["content-type"]

    def test_export_invalid_report_type_returns_400(self, client, admin_headers):
        resp = client.post(
            "/api/v1/reports/export",
            json={"report_type": "unknown-report"},
            headers=admin_headers,
        )
        assert resp.status_code == 400
        assert "Unsupported report_type" in resp.json()["detail"]

    def test_export_with_date_range_filter(self, client, admin_headers, seeded_report_data):
        today = date.today()
        resp = client.post(
            "/api/v1/reports/export",
            json={
                "report_type": "consumption",
                "start_date": str(today - timedelta(days=7)),
                "end_date": str(today),
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers["content-type"]
