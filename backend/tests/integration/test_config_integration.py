"""
Integration tests for Configuration API endpoints.

Covers:
- GET  /api/v1/config
- GET  /api/v1/config/conversion-ratios
- PUT  /api/v1/config/conversion-ratios  (Admin only)
- GET  /api/v1/config/thresholds
- PUT  /api/v1/config/thresholds  (Admin only)
- GET  /api/v1/config/{key}
- PUT  /api/v1/config/{key}  (Admin only)
- RBAC enforcement
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.models.system_config import SystemConfig
from app.models.medical_supply import MedicalSupply
from app.models.conversion_ratio import ConversionRatio
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
def pharmacist_user(db_session):
    user = User(
        username="pharmacist",
        email="pharmacist@test.com",
        password_hash=hash_password("pharmapass123"),
        full_name="Pharmacist User",
        role="Pharmacist",
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
def pharmacist_headers(pharmacist_user):
    token = create_access_token(data={"sub": pharmacist_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_config(db_session, admin_user):
    config = SystemConfig(
        config_key="test_key",
        config_value="test_value",
        description="Test configuration",
        updated_by=admin_user.id,
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return config


@pytest.fixture
def sample_supply(db_session):
    supply = MedicalSupply(
        name="Surgical Mask",
        category="PPE",
        unit="box",
    )
    db_session.add(supply)
    db_session.commit()
    db_session.refresh(supply)
    return supply


@pytest.fixture
def sample_conversion_ratio(db_session, sample_supply, admin_user):
    ratio = ConversionRatio(
        disease_type="dengue_fever",
        supply_id=sample_supply.id,
        ratio=2.0,
        unit="box",
        updated_by=admin_user.id,
    )
    db_session.add(ratio)
    db_session.commit()
    db_session.refresh(ratio)
    return ratio


# ── List Configs Tests ────────────────────────────────────────────────────────

class TestListConfigs:
    def test_list_configs_requires_auth(self, client):
        resp = client.get("/api/v1/config")
        assert resp.status_code == 401

    def test_list_configs_returns_list(self, client, admin_headers):
        resp = client.get("/api/v1/config", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_configs_with_data(self, client, admin_headers, sample_config):
        resp = client.get("/api/v1/config", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert any(c["config_key"] == "test_key" for c in data)

    def test_list_configs_accessible_by_pharmacist(self, client, pharmacist_headers):
        resp = client.get("/api/v1/config", headers=pharmacist_headers)
        assert resp.status_code == 200


# ── Get Config by Key Tests ───────────────────────────────────────────────────

class TestGetConfigByKey:
    def test_get_config_by_key_success(self, client, admin_headers, sample_config):
        resp = client.get("/api/v1/config/test_key", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["config_key"] == "test_key"
        assert data["config_value"] == "test_value"

    def test_get_config_by_key_not_found(self, client, admin_headers):
        resp = client.get("/api/v1/config/nonexistent_key", headers=admin_headers)
        assert resp.status_code == 404

    def test_get_config_by_key_requires_auth(self, client):
        resp = client.get("/api/v1/config/some_key")
        assert resp.status_code == 401


# ── Update Config by Key Tests ────────────────────────────────────────────────

class TestUpdateConfigByKey:
    def test_update_config_success_as_admin(self, client, admin_headers, sample_config):
        resp = client.put(
            "/api/v1/config/test_key",
            json={"config_value": "updated_value", "description": "Updated"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["config_value"] == "updated_value"

    def test_update_config_forbidden_for_pharmacist(self, client, pharmacist_headers, sample_config):
        resp = client.put(
            "/api/v1/config/test_key",
            json={"value": "new_value"},
            headers=pharmacist_headers,
        )
        assert resp.status_code == 403

    def test_create_new_config_via_put(self, client, admin_headers):
        """PUT to a nonexistent key should create it."""
        resp = client.put(
            "/api/v1/config/new_key",
            json={"config_value": "new_value", "description": "Brand new config"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["config_key"] == "new_key"
        assert data["config_value"] == "new_value"

    def test_update_config_requires_auth(self, client):
        resp = client.put(
            "/api/v1/config/some_key",
            json={"config_value": "v"},
        )
        assert resp.status_code == 401


# ── Conversion Ratios Tests ───────────────────────────────────────────────────

class TestConversionRatios:
    def test_get_conversion_ratios_requires_auth(self, client):
        resp = client.get("/api/v1/config/conversion-ratios")
        assert resp.status_code == 401

    def test_get_conversion_ratios_returns_list(self, client, admin_headers):
        resp = client.get("/api/v1/config/conversion-ratios", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_conversion_ratios_returns_data(
        self, client, admin_headers, sample_conversion_ratio
    ):
        resp = client.get("/api/v1/config/conversion-ratios", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert any(r["disease_type"] == "dengue_fever" for r in data)

    def test_get_conversion_ratios_pharmacist_can_read(
        self, client, pharmacist_headers
    ):
        resp = client.get("/api/v1/config/conversion-ratios", headers=pharmacist_headers)
        assert resp.status_code == 200

    def test_update_conversion_ratios_requires_admin(
        self, client, pharmacist_headers, sample_supply
    ):
        payload = {
            "ratios": [
                {
                    "disease_type": "dengue_fever",
                    "supply_id": sample_supply.id,
                    "ratio": 3.0,
                    "unit": "box",
                }
            ]
        }
        resp = client.put(
            "/api/v1/config/conversion-ratios",
            json=payload,
            headers=pharmacist_headers,
        )
        assert resp.status_code == 403

    def test_update_conversion_ratios_as_admin(
        self, client, admin_headers, sample_supply
    ):
        payload = {
            "ratios": [
                {
                    "disease_type": "dengue_fever",
                    "supply_id": sample_supply.id,
                    "ratio": 3.0,
                    "unit": "box",
                }
            ]
        }
        resp = client.put(
            "/api/v1/config/conversion-ratios",
            json=payload,
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data[0]["ratio"] == 3.0


# ── Thresholds Tests ──────────────────────────────────────────────────────────

class TestThresholds:
    def test_get_thresholds_requires_auth(self, client):
        resp = client.get("/api/v1/config/thresholds")
        assert resp.status_code == 401

    def test_get_thresholds_returns_structure(self, client, admin_headers):
        resp = client.get("/api/v1/config/thresholds", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "critical_days" in data
        assert "high_days" in data
        assert "medium_days" in data

    def test_get_thresholds_pharmacist_can_read(self, client, pharmacist_headers):
        resp = client.get("/api/v1/config/thresholds", headers=pharmacist_headers)
        assert resp.status_code == 200

    def test_update_thresholds_requires_admin(self, client, pharmacist_headers):
        resp = client.put(
            "/api/v1/config/thresholds",
            json={"critical_days": 3, "high_days": 7, "medium_days": 14},
            headers=pharmacist_headers,
        )
        assert resp.status_code == 403

    def test_update_thresholds_as_admin(self, client, admin_headers):
        resp = client.put(
            "/api/v1/config/thresholds",
            json={"critical_days": 3, "high_days": 7, "medium_days": 14},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["critical_days"] == 3
        assert data["high_days"] == 7
        assert data["medium_days"] == 14

    def test_update_thresholds_invalid_order_rejected(self, client, admin_headers):
        """critical_days must be < high_days < medium_days."""
        resp = client.put(
            "/api/v1/config/thresholds",
            json={"critical_days": 14, "high_days": 7, "medium_days": 3},
            headers=admin_headers,
        )
        assert resp.status_code in [400, 422]
