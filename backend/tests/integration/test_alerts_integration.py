"""
Integration tests for Alerts API endpoints.

Covers:
- GET  /api/v1/alerts
- GET  /api/v1/alerts/active
- GET  /api/v1/alerts/critical
- GET  /api/v1/alerts/{id}
- PUT  /api/v1/alerts/{id}/resolve
- POST /api/v1/alerts/check
- Filtering, error handling, RBAC
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
def sample_supply(db_session):
    supply = MedicalSupply(
        name="Surgical Mask", category="PPE", unit="box", unit_price=10.0
    )
    db_session.add(supply)
    db_session.commit()
    db_session.refresh(supply)
    return supply


@pytest.fixture
def seeded_alerts(db_session, sample_supply):
    """Create a mix of resolved and unresolved alerts at different severities."""
    alerts = [
        Alert(
            supply_id=sample_supply.id,
            alert_type="shortage",
            severity="critical",
            current_stock=5,
            required_stock=200,
            shortage_date=date.today() + timedelta(days=2),
            message="Critical shortage of Surgical Mask",
            is_resolved=False,
        ),
        Alert(
            supply_id=sample_supply.id,
            alert_type="shortage",
            severity="high",
            current_stock=30,
            required_stock=200,
            shortage_date=date.today() + timedelta(days=5),
            message="High shortage risk",
            is_resolved=False,
        ),
        Alert(
            supply_id=sample_supply.id,
            alert_type="shortage",
            severity="medium",
            current_stock=80,
            required_stock=200,
            shortage_date=date.today() + timedelta(days=10),
            message="Medium shortage risk",
            is_resolved=False,
        ),
        Alert(
            supply_id=sample_supply.id,
            alert_type="shortage",
            severity="critical",
            current_stock=0,
            required_stock=100,
            shortage_date=date.today() - timedelta(days=1),
            message="Resolved alert",
            is_resolved=True,
        ),
    ]
    db_session.add_all(alerts)
    db_session.commit()
    return alerts


# ── List Alerts Tests ─────────────────────────────────────────────────────────

class TestListAlerts:
    def test_list_alerts_requires_auth(self, client):
        resp = client.get("/api/v1/alerts")
        assert resp.status_code == 401

    def test_list_alerts_returns_all(self, client, admin_headers, seeded_alerts):
        resp = client.get("/api/v1/alerts", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4  # All alerts including resolved

    def test_list_alerts_filter_by_severity_critical(
        self, client, admin_headers, seeded_alerts
    ):
        resp = client.get("/api/v1/alerts?severity=critical", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2  # 1 unresolved + 1 resolved critical
        for alert in data:
            assert alert["severity"] == "critical"

    def test_list_alerts_filter_by_is_resolved_false(
        self, client, admin_headers, seeded_alerts
    ):
        resp = client.get(
            "/api/v1/alerts?is_resolved=false", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3  # 3 unresolved
        for alert in data:
            assert alert["is_resolved"] is False

    def test_list_alerts_filter_by_is_resolved_true(
        self, client, admin_headers, seeded_alerts
    ):
        resp = client.get(
            "/api/v1/alerts?is_resolved=true", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["is_resolved"] is True

    def test_list_alerts_filter_by_supply_id(
        self, client, admin_headers, seeded_alerts, sample_supply
    ):
        resp = client.get(
            f"/api/v1/alerts?supply_id={sample_supply.id}", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4
        for alert in data:
            assert alert["supply_id"] == sample_supply.id

    def test_list_alerts_pagination(self, client, admin_headers, seeded_alerts):
        resp = client.get(
            "/api/v1/alerts?limit=2&offset=0", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_list_alerts_invalid_severity(self, client, admin_headers):
        resp = client.get(
            "/api/v1/alerts?severity=invalid", headers=admin_headers
        )
        assert resp.status_code == 422

    def test_alert_has_expected_fields(self, client, admin_headers, seeded_alerts):
        resp = client.get("/api/v1/alerts", headers=admin_headers)
        alert = resp.json()[0]
        for field in ["id", "supply_id", "severity", "current_stock", "required_stock", "is_resolved", "created_at"]:
            assert field in alert


# ── Active Alerts Tests ───────────────────────────────────────────────────────

class TestActiveAlerts:
    def test_active_alerts_requires_auth(self, client):
        resp = client.get("/api/v1/alerts/active")
        assert resp.status_code == 401

    def test_active_alerts_returns_only_unresolved(
        self, client, admin_headers, seeded_alerts
    ):
        resp = client.get("/api/v1/alerts/active", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        for alert in data:
            assert alert["is_resolved"] is False

    def test_active_alerts_filter_by_severity(
        self, client, admin_headers, seeded_alerts
    ):
        resp = client.get(
            "/api/v1/alerts/active?severity=high", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["severity"] == "high"

    def test_active_alerts_empty_when_all_resolved(self, client, admin_headers, db_session, sample_supply):
        resolved_alert = Alert(
            supply_id=sample_supply.id,
            alert_type="shortage",
            severity="critical",
            current_stock=0,
            required_stock=100,
            shortage_date=date.today(),
            message="Already resolved",
            is_resolved=True,
        )
        db_session.add(resolved_alert)
        db_session.commit()

        resp = client.get("/api/v1/alerts/active", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json() == []


# ── Critical Alerts Tests ─────────────────────────────────────────────────────

class TestCriticalAlerts:
    def test_critical_alerts_requires_auth(self, client):
        resp = client.get("/api/v1/alerts/critical")
        assert resp.status_code == 401

    def test_critical_alerts_returns_only_critical_unresolved(
        self, client, admin_headers, seeded_alerts
    ):
        resp = client.get("/api/v1/alerts/critical", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Only 1 unresolved critical
        assert len(data) == 1
        assert data[0]["severity"] == "critical"
        assert data[0]["is_resolved"] is False


# ── Get Alert by ID Tests ─────────────────────────────────────────────────────

class TestGetAlertById:
    def test_get_alert_by_id_success(self, client, admin_headers, seeded_alerts):
        alert_id = seeded_alerts[0].id
        resp = client.get(f"/api/v1/alerts/{alert_id}", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == alert_id
        assert data["severity"] == "critical"
        assert "supply_name" in data

    def test_get_alert_by_id_not_found(self, client, admin_headers):
        resp = client.get("/api/v1/alerts/99999", headers=admin_headers)
        assert resp.status_code == 404

    def test_get_alert_by_id_requires_auth(self, client, seeded_alerts):
        resp = client.get(f"/api/v1/alerts/{seeded_alerts[0].id}")
        assert resp.status_code == 401


# ── Resolve Alert Tests ───────────────────────────────────────────────────────

class TestResolveAlert:
    def test_resolve_alert_success(
        self, client, admin_headers, seeded_alerts, db_session
    ):
        unresolved = seeded_alerts[0]
        assert unresolved.is_resolved is False

        resp = client.put(
            f"/api/v1/alerts/{unresolved.id}/resolve",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_resolved"] is True
        assert data["resolved_at"] is not None

    def test_resolve_alert_not_found_returns_404(self, client, admin_headers):
        resp = client.put(
            "/api/v1/alerts/99999/resolve",
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_resolve_already_resolved_is_idempotent(
        self, client, admin_headers, seeded_alerts
    ):
        # Alert index 3 is already resolved
        resolved = seeded_alerts[3]
        resp = client.put(
            f"/api/v1/alerts/{resolved.id}/resolve",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_resolved"] is True

    def test_resolve_alert_requires_auth(self, client, seeded_alerts):
        resp = client.put(f"/api/v1/alerts/{seeded_alerts[0].id}/resolve")
        assert resp.status_code == 401


# ── Alert Check Tests ─────────────────────────────────────────────────────────

class TestAlertCheck:
    def test_alert_check_requires_auth(self, client):
        resp = client.post("/api/v1/alerts/check")
        assert resp.status_code == 401

    def test_alert_check_returns_summary(self, client, admin_headers):
        resp = client.post("/api/v1/alerts/check", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert "alerts_generated" in data
        assert "critical_alerts" in data
        assert "high_alerts" in data
        assert "medium_alerts" in data

    def test_alert_check_with_no_requirements_generates_zero(
        self, client, admin_headers
    ):
        resp = client.post("/api/v1/alerts/check", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["alerts_generated"] == 0
