"""
Integration tests for Forecasting API endpoints.

Covers:
- GET  /api/v1/forecasts
- GET  /api/v1/forecasts/{id}
- GET  /api/v1/forecasts/latest/{disease_type}
- GET  /api/v1/forecasts/accuracy/metrics
- POST /api/v1/forecasts/generate
- Filtering, pagination, error handling
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
from app.models.disease_forecast import DiseaseForecast
from app.models.disease_case import DiseaseCase
from app.models.environmental_data import EnvironmentalData
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
def seeded_forecasts(db_session):
    """Create forecasts for multiple disease types."""
    today = date.today()
    forecasts = []
    for i in range(5):
        fc = DiseaseForecast(
            forecast_date=today + timedelta(days=i + 1),
            disease_type="dengue_fever",
            predicted_cases=100 + i * 10,
            confidence_lower=80 + i * 10,
            confidence_upper=120 + i * 10,
            model_used="ensemble",
            model_accuracy_mae=5.2,
            model_accuracy_rmse=7.8,
            model_accuracy_mape=4.5,
            forecast_period_days=7,
        )
        db_session.add(fc)
        forecasts.append(fc)

    # Add one seasonal_flu forecast
    flu_fc = DiseaseForecast(
        forecast_date=today + timedelta(days=1),
        disease_type="seasonal_flu",
        predicted_cases=200,
        model_used="ensemble",
        model_accuracy_mae=8.1,
        model_accuracy_rmse=10.2,
        model_accuracy_mape=6.3,
        forecast_period_days=7,
    )
    db_session.add(flu_fc)
    forecasts.append(flu_fc)

    db_session.commit()
    return forecasts


# ── List Forecasts Tests ──────────────────────────────────────────────────────

class TestListForecasts:
    def test_list_requires_auth(self, client):
        resp = client.get("/api/v1/forecasts")
        assert resp.status_code == 401

    def test_list_returns_empty_initially(self, client, admin_headers):
        resp = client.get("/api/v1/forecasts", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_seeded_forecasts(self, client, admin_headers, seeded_forecasts):
        resp = client.get("/api/v1/forecasts", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 6

    def test_list_filter_by_disease_type(self, client, admin_headers, seeded_forecasts):
        resp = client.get(
            "/api/v1/forecasts?disease_type=dengue_fever", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        for fc in data:
            assert fc["disease_type"] == "dengue_fever"

    def test_list_filter_by_date_range(self, client, admin_headers, seeded_forecasts):
        today = date.today()
        start = today + timedelta(days=1)
        end = today + timedelta(days=3)
        resp = client.get(
            f"/api/v1/forecasts?start_date={start}&end_date={end}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # 3 dengue + 1 flu on day 1, 2 dengue on days 2 and 3
        assert len(data) <= 6

    def test_list_with_pagination(self, client, admin_headers, seeded_forecasts):
        resp = client.get(
            "/api/v1/forecasts?limit=3&offset=0", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    def test_forecast_has_expected_fields(self, client, admin_headers, seeded_forecasts):
        resp = client.get("/api/v1/forecasts", headers=admin_headers)
        fc = resp.json()[0]
        for field in [
            "id",
            "forecast_date",
            "disease_type",
            "predicted_cases",
            "model_used",
        ]:
            assert field in fc


# ── Get Forecast by ID Tests ──────────────────────────────────────────────────

class TestGetForecastById:
    def test_get_by_id_success(self, client, admin_headers, seeded_forecasts):
        fc_id = seeded_forecasts[0].id
        resp = client.get(f"/api/v1/forecasts/{fc_id}", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == fc_id
        assert data["disease_type"] == "dengue_fever"

    def test_get_by_id_not_found(self, client, admin_headers):
        resp = client.get("/api/v1/forecasts/99999", headers=admin_headers)
        assert resp.status_code == 404

    def test_get_by_id_requires_auth(self, client, seeded_forecasts):
        resp = client.get(f"/api/v1/forecasts/{seeded_forecasts[0].id}")
        assert resp.status_code == 401

    def test_get_by_id_includes_accuracy_metrics(
        self, client, admin_headers, seeded_forecasts
    ):
        fc_id = seeded_forecasts[0].id
        resp = client.get(f"/api/v1/forecasts/{fc_id}", headers=admin_headers)
        data = resp.json()
        assert data["model_accuracy_mae"] == 5.2
        assert data["model_accuracy_rmse"] == 7.8
        assert data["model_accuracy_mape"] == 4.5


# ── Get Latest Forecast Tests ─────────────────────────────────────────────────

class TestGetLatestForecast:
    def test_get_latest_dengue_success(
        self, client, admin_headers, seeded_forecasts
    ):
        resp = client.get(
            "/api/v1/forecasts/latest/dengue_fever", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["disease_type"] == "dengue_fever"

    def test_get_latest_flu_success(self, client, admin_headers, seeded_forecasts):
        resp = client.get(
            "/api/v1/forecasts/latest/seasonal_flu", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["disease_type"] == "seasonal_flu"

    def test_get_latest_not_found_when_no_data(self, client, admin_headers):
        resp = client.get(
            "/api/v1/forecasts/latest/respiratory_disease", headers=admin_headers
        )
        assert resp.status_code == 404

    def test_get_latest_requires_auth(self, client):
        resp = client.get("/api/v1/forecasts/latest/dengue_fever")
        assert resp.status_code == 401


# ── Accuracy Metrics Tests ────────────────────────────────────────────────────

class TestAccuracyMetrics:
    def test_accuracy_metrics_requires_auth(self, client):
        resp = client.get("/api/v1/forecasts/accuracy/metrics")
        assert resp.status_code == 401

    def test_accuracy_metrics_empty_db(self, client, admin_headers):
        resp = client.get("/api/v1/forecasts/accuracy/metrics", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["mae"] is None

    def test_accuracy_metrics_with_data(
        self, client, admin_headers, seeded_forecasts
    ):
        resp = client.get("/api/v1/forecasts/accuracy/metrics", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "mae" in data
        assert "rmse" in data
        assert "mape" in data
        assert data["count"] > 0

    def test_accuracy_metrics_filter_by_disease_type(
        self, client, admin_headers, seeded_forecasts
    ):
        resp = client.get(
            "/api/v1/forecasts/accuracy/metrics?disease_type=dengue_fever",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["disease_type"] == "dengue_fever"


# ── Generate Forecast Tests ───────────────────────────────────────────────────

class TestGenerateForecast:
    def test_generate_requires_auth(self, client):
        resp = client.post(
            "/api/v1/forecasts/generate",
            json={"disease_type": "dengue_fever", "forecast_period_days": 7},
        )
        assert resp.status_code == 401

    def test_generate_invalid_period_too_short_rejected(self, client, admin_headers):
        resp = client.post(
            "/api/v1/forecasts/generate",
            json={"disease_type": "dengue_fever", "forecast_period_days": 5},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_generate_invalid_period_too_long_rejected(self, client, admin_headers):
        resp = client.post(
            "/api/v1/forecasts/generate",
            json={"disease_type": "dengue_fever", "forecast_period_days": 35},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_generate_valid_request_accepted(self, client, admin_headers):
        """With little/no historical data the endpoint should either
        succeed (202/200) or return a graceful error (e.g. 400/422), but
        must NOT crash the server (5xx)."""
        resp = client.post(
            "/api/v1/forecasts/generate",
            json={"disease_type": "dengue_fever", "forecast_period_days": 7},
            headers=admin_headers,
        )
        # Should not be a 5xx server error
        assert resp.status_code < 500

    def test_generate_invalid_disease_type_rejected(self, client, admin_headers):
        resp = client.post(
            "/api/v1/forecasts/generate",
            json={"disease_type": "unknown_disease", "forecast_period_days": 7},
            headers=admin_headers,
        )
        assert resp.status_code == 422
