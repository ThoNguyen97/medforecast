"""
Integration tests for Audit & Logs API endpoints.

Covers:
- GET  /api/v1/audit-logs
- GET  /api/v1/system-logs
- GET  /api/v1/system-logs/errors
- POST /api/v1/system-logs/cleanup
- Pagination and filtering
- Admin-only access enforcement
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.system_log import SystemLog
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
def seeded_audit_logs(db_session, admin_user):
    """Create sample audit log entries."""
    logs = [
        AuditLog(
            user_id=admin_user.id,
            action="CREATE",
            table_name="medical_supplies",
            record_id=1,
            old_value=None,
            new_value={"name": "Mask"},
            ip_address="127.0.0.1",
        ),
        AuditLog(
            user_id=admin_user.id,
            action="UPDATE",
            table_name="inventory",
            record_id=2,
            old_value={"current_stock": 100},
            new_value={"current_stock": 200},
            ip_address="127.0.0.1",
        ),
        AuditLog(
            user_id=admin_user.id,
            action="DELETE",
            table_name="medical_supplies",
            record_id=3,
            ip_address="10.0.0.1",
        ),
    ]
    db_session.add_all(logs)
    db_session.commit()
    return logs


@pytest.fixture
def seeded_system_logs(db_session):
    """Create sample system log entries."""
    logs = [
        SystemLog(
            log_level="ERROR",
            module_name="forecasting",
            message="Forecast failed",
            stack_trace="Traceback...",
        ),
        SystemLog(
            log_level="WARNING",
            module_name="data_collector",
            message="Retry attempt 1",
        ),
        SystemLog(
            log_level="INFO",
            module_name="api",
            message="Request processed successfully",
        ),
        SystemLog(
            log_level="ERROR",
            module_name="database",
            message="Connection timeout",
        ),
    ]
    db_session.add_all(logs)
    db_session.commit()
    return logs


# ── Audit Logs Tests ──────────────────────────────────────────────────────────

class TestAuditLogs:
    def test_audit_logs_requires_auth(self, client):
        resp = client.get("/api/v1/audit-logs")
        assert resp.status_code == 401

    def test_audit_logs_requires_admin(self, client, pharmacist_headers):
        resp = client.get("/api/v1/audit-logs", headers=pharmacist_headers)
        assert resp.status_code == 403

    def test_audit_logs_admin_can_access(self, client, admin_headers):
        resp = client.get("/api/v1/audit-logs", headers=admin_headers)
        assert resp.status_code == 200

    def test_audit_logs_returns_paginated_structure(self, client, admin_headers):
        resp = client.get("/api/v1/audit-logs", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_audit_logs_returns_seeded_data(self, client, admin_headers, seeded_audit_logs):
        resp = client.get("/api/v1/audit-logs", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_audit_logs_filter_by_action(self, client, admin_headers, seeded_audit_logs):
        resp = client.get("/api/v1/audit-logs?action=CREATE", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["action"] == "CREATE"

    def test_audit_logs_filter_by_table_name(self, client, admin_headers, seeded_audit_logs):
        resp = client.get(
            "/api/v1/audit-logs?table_name=medical_supplies", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_audit_logs_filter_by_user_id(
        self, client, admin_headers, seeded_audit_logs, admin_user
    ):
        resp = client.get(
            f"/api/v1/audit-logs?user_id={admin_user.id}", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    def test_audit_logs_pagination(self, client, admin_headers, seeded_audit_logs):
        resp = client.get(
            "/api/v1/audit-logs?page=1&page_size=2", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2

    def test_audit_logs_pagination_page_2(self, client, admin_headers, seeded_audit_logs):
        resp = client.get(
            "/api/v1/audit-logs?page=2&page_size=2", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1  # 3 total, 2 on page 1, 1 on page 2

    def test_audit_logs_item_has_expected_fields(
        self, client, admin_headers, seeded_audit_logs
    ):
        resp = client.get("/api/v1/audit-logs", headers=admin_headers)
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert "id" in item
        assert "action" in item
        assert "table_name" in item
        assert "created_at" in item


# ── System Logs Tests ─────────────────────────────────────────────────────────

class TestSystemLogs:
    def test_system_logs_requires_auth(self, client):
        resp = client.get("/api/v1/system-logs")
        assert resp.status_code == 401

    def test_system_logs_requires_admin(self, client, pharmacist_headers):
        resp = client.get("/api/v1/system-logs", headers=pharmacist_headers)
        assert resp.status_code == 403

    def test_system_logs_admin_can_access(self, client, admin_headers):
        resp = client.get("/api/v1/system-logs", headers=admin_headers)
        assert resp.status_code == 200

    def test_system_logs_returns_paginated_structure(self, client, admin_headers):
        resp = client.get("/api/v1/system-logs", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "items" in data

    def test_system_logs_returns_seeded_data(
        self, client, admin_headers, seeded_system_logs
    ):
        resp = client.get("/api/v1/system-logs", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    def test_system_logs_filter_by_log_level(
        self, client, admin_headers, seeded_system_logs
    ):
        resp = client.get(
            "/api/v1/system-logs?log_level=ERROR", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["log_level"] == "ERROR"

    def test_system_logs_filter_by_module_name(
        self, client, admin_headers, seeded_system_logs
    ):
        resp = client.get(
            "/api/v1/system-logs?module_name=forecasting", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_system_logs_invalid_log_level_rejected(self, client, admin_headers):
        resp = client.get(
            "/api/v1/system-logs?log_level=INVALID", headers=admin_headers
        )
        assert resp.status_code == 422


# ── Error Logs Tests ──────────────────────────────────────────────────────────

class TestErrorLogs:
    def test_error_logs_requires_auth(self, client):
        resp = client.get("/api/v1/system-logs/errors")
        assert resp.status_code == 401

    def test_error_logs_requires_admin(self, client, pharmacist_headers):
        resp = client.get("/api/v1/system-logs/errors", headers=pharmacist_headers)
        assert resp.status_code == 403

    def test_error_logs_returns_only_errors(
        self, client, admin_headers, seeded_system_logs
    ):
        resp = client.get("/api/v1/system-logs/errors", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["log_level"] == "ERROR"

    def test_error_logs_filter_by_module(
        self, client, admin_headers, seeded_system_logs
    ):
        resp = client.get(
            "/api/v1/system-logs/errors?module_name=database", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["module_name"] == "database"


# ── Log Cleanup Tests ─────────────────────────────────────────────────────────

class TestLogCleanup:
    def test_cleanup_requires_auth(self, client):
        resp = client.post("/api/v1/system-logs/cleanup")
        assert resp.status_code == 401

    def test_cleanup_requires_admin(self, client, pharmacist_headers):
        resp = client.post("/api/v1/system-logs/cleanup", headers=pharmacist_headers)
        assert resp.status_code == 403

    def test_cleanup_admin_triggers_successfully(self, client, admin_headers):
        resp = client.post("/api/v1/system-logs/cleanup", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert "retention_days" in data

    def test_cleanup_with_custom_retention_days(self, client, admin_headers):
        resp = client.post(
            "/api/v1/system-logs/cleanup?retention_days=30", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["retention_days"] == 30

    def test_cleanup_invalid_retention_days(self, client, admin_headers):
        resp = client.post(
            "/api/v1/system-logs/cleanup?retention_days=0", headers=admin_headers
        )
        assert resp.status_code == 422
