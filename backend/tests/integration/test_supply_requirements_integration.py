"""
Integration tests for Supply Requirements API endpoints.

Covers:
- GET  /api/v1/supply-requirements
- GET  /api/v1/supply-requirements/summary
- GET  /api/v1/supply-requirements/forecast/{forecast_id}
- POST /api/v1/supply-requirements/generate/{forecast_id}
- Filtering and error handling
"""

import pytest
from datetime import date, datetime
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
def sample_supply(db_session):
    supply = MedicalSupply(name="Surgical Mask", category="PPE", unit="box")
    db_session.add(supply)
    db_session.commit()
    db_session.refresh(supply)
    return supply


@pytest.fixture
def sample_inventory(db_session, sample_supply, admin_user):
    inv = Inventory(
        supply_id=sample_supply.id,
        current_stock=500,
        safety_stock=100,
        updated_by=admin_user.id,
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


@pytest.fixture
def sample_forecast(db_session):
    fc = DiseaseForecast(
        forecast_date=date.today(),
        disease_type="dengue_fever",
        predicted_cases=100,
        model_used="ensemble",
        created_at=datetime.utcnow(),
    )
    db_session.add(fc)
    db_session.commit()
    db_session.refresh(fc)
    return fc


@pytest.fixture
def sample_requirement(db_session, sample_forecast, sample_supply):
    req = SupplyRequirement(
        forecast_id=sample_forecast.id,
        supply_id=sample_supply.id,
        required_quantity=200,
        requirement_date=date.today(),
        disease_type="dengue_fever",
    )
    db_session.add(req)
    db_session.commit()
    db_session.refresh(req)
    return req


# ── List Supply Requirements Tests ───────────────────────────────────────────

class TestListSupplyRequirements:
    def test_list_requires_auth(self, client):
        resp = client.get("/api/v1/supply-requirements")
        assert resp.status_code == 401

    def test_list_returns_empty_initially(self, client, admin_headers):
        resp = client.get("/api/v1/supply-requirements", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_seeded_data(
        self, client, admin_headers, sample_requirement, sample_inventory
    ):
        resp = client.get("/api/v1/supply-requirements", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        item = data[0]
        assert item["required_quantity"] == 200
        assert item["disease_type"] == "dengue_fever"
        assert "supply_name" in item
        assert "current_stock" in item
        assert "shortage_amount" in item

    def test_list_filter_by_forecast_id(
        self, client, admin_headers, sample_requirement, sample_forecast
    ):
        resp = client.get(
            f"/api/v1/supply-requirements?forecast_id={sample_forecast.id}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    def test_list_filter_by_supply_id(
        self, client, admin_headers, sample_requirement, sample_supply
    ):
        resp = client.get(
            f"/api/v1/supply-requirements?supply_id={sample_supply.id}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["supply_name"] == "Surgical Mask"

    def test_list_filter_by_disease_type(
        self, client, admin_headers, sample_requirement
    ):
        resp = client.get(
            "/api/v1/supply-requirements?disease_type=dengue_fever",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["disease_type"] == "dengue_fever"

    def test_list_shortage_amount_calculation(
        self, client, admin_headers, sample_requirement, sample_inventory
    ):
        """shortage_amount = max(0, required - current_stock)."""
        resp = client.get("/api/v1/supply-requirements", headers=admin_headers)
        assert resp.status_code == 200
        item = resp.json()[0]
        # required=200, current_stock=500 → no shortage
        assert item["shortage_amount"] == 0

    def test_list_shows_shortage_when_stock_insufficient(
        self, client, admin_headers, db_session, sample_supply, sample_forecast
    ):
        # Low inventory
        inv = Inventory(
            supply_id=sample_supply.id,
            current_stock=50,
            safety_stock=20,
        )
        db_session.add(inv)
        req = SupplyRequirement(
            forecast_id=sample_forecast.id,
            supply_id=sample_supply.id,
            required_quantity=200,
            requirement_date=date.today(),
            disease_type="dengue_fever",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.get("/api/v1/supply-requirements", headers=admin_headers)
        assert resp.status_code == 200
        item = resp.json()[0]
        assert item["shortage_amount"] == 150  # 200 - 50


# ── Summary Tests ─────────────────────────────────────────────────────────────

class TestSupplyRequirementsSummary:
    def test_summary_requires_auth(self, client):
        resp = client.get("/api/v1/supply-requirements/summary")
        assert resp.status_code == 401

    def test_summary_empty_db(self, client, admin_headers):
        resp = client.get("/api/v1/supply-requirements/summary", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_supplies"] == 0
        assert data["supplies_with_shortage"] == 0
        assert data["items"] == []

    def test_summary_with_data(
        self, client, admin_headers, sample_requirement, sample_inventory
    ):
        resp = client.get("/api/v1/supply-requirements/summary", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_supplies"] == 1
        assert "items" in data
        assert len(data["items"]) == 1

    def test_summary_filter_by_disease_type(
        self, client, admin_headers, sample_requirement
    ):
        resp = client.get(
            "/api/v1/supply-requirements/summary?disease_type=dengue_fever",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_supplies"] >= 0


# ── Get Requirements for Forecast Tests ──────────────────────────────────────

class TestGetRequirementsForForecast:
    def test_get_requirements_for_forecast_success(
        self, client, admin_headers, sample_requirement, sample_forecast
    ):
        resp = client.get(
            f"/api/v1/supply-requirements/forecast/{sample_forecast.id}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["forecast_id"] == sample_forecast.id

    def test_get_requirements_for_nonexistent_forecast(self, client, admin_headers):
        resp = client.get(
            "/api/v1/supply-requirements/forecast/99999",
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_get_requirements_for_forecast_requires_auth(
        self, client, sample_forecast
    ):
        resp = client.get(
            f"/api/v1/supply-requirements/forecast/{sample_forecast.id}"
        )
        assert resp.status_code == 401


# ── Generate Requirements Tests ───────────────────────────────────────────────

class TestGenerateRequirementsForForecast:
    def test_generate_for_nonexistent_forecast_returns_404(
        self, client, admin_headers
    ):
        resp = client.post(
            "/api/v1/supply-requirements/generate/99999",
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_generate_requires_auth(self, client, sample_forecast):
        resp = client.post(
            f"/api/v1/supply-requirements/generate/{sample_forecast.id}"
        )
        assert resp.status_code == 401

    def test_generate_for_valid_forecast_returns_201(
        self, client, admin_headers, sample_forecast
    ):
        resp = client.post(
            f"/api/v1/supply-requirements/generate/{sample_forecast.id}",
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "forecast_id" in data
        assert "requirements_count" in data
        assert data["forecast_id"] == sample_forecast.id
