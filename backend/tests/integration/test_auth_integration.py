"""
Integration tests for Authentication & Authorization flows.

Covers:
- POST /api/v1/auth/login
- POST /api/v1/auth/logout
- GET  /api/v1/auth/me
- POST /api/v1/auth/refresh
- JWT token validation
- Inactive user handling
- Protected route enforcement
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.user import User
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
def active_admin(db_session):
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
def inactive_user(db_session):
    user = User(
        username="inactive",
        email="inactive@test.com",
        password_hash=hash_password("pass123"),
        full_name="Inactive User",
        role="Pharmacist",
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ── Login Tests ───────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_success_returns_token(self, client, active_admin):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

    def test_login_wrong_username_returns_401(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "pass123"},
        )
        assert resp.status_code == 401
        assert "Incorrect username or password" in resp.json()["detail"]

    def test_login_wrong_password_returns_401(self, client, active_admin):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert "Incorrect username or password" in resp.json()["detail"]

    def test_login_inactive_user_returns_400(self, client, inactive_user):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "inactive", "password": "pass123"},
        )
        assert resp.status_code == 400
        assert "Inactive user" in resp.json()["detail"]

    def test_login_missing_fields_returns_422(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "admin"})
        assert resp.status_code == 422

    def test_login_empty_credentials_returns_422_or_401(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "", "password": ""},
        )
        assert resp.status_code in [401, 422]


# ── Get Current User Tests ────────────────────────────────────────────────────

class TestGetCurrentUser:
    def test_get_me_with_valid_token(self, client, active_admin):
        token = create_access_token(data={"sub": active_admin.username})
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "admin"
        assert data["email"] == "admin@test.com"
        assert data["role"] == "Administrator"
        assert "password_hash" not in data

    def test_get_me_without_token_returns_401(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_get_me_invalid_token_returns_401(self, client):
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    def test_get_me_malformed_auth_header_returns_401(self, client):
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "NotBearer token"},
        )
        assert resp.status_code == 401


# ── Refresh Token Tests ───────────────────────────────────────────────────────

class TestRefreshToken:
    def test_refresh_token_returns_new_token(self, client, active_admin):
        token = create_access_token(data={"sub": active_admin.username})
        resp = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

    def test_refresh_token_invalid_token_returns_401(self, client):
        resp = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": "Bearer bad_token"},
        )
        assert resp.status_code == 401

    def test_refresh_token_no_auth_returns_401(self, client):
        resp = client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401


# ── Logout Tests ──────────────────────────────────────────────────────────────

class TestLogout:
    def test_logout_with_valid_token(self, client, active_admin):
        token = create_access_token(data={"sub": active_admin.username})
        resp = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "logged out" in resp.json()["message"].lower()

    def test_logout_without_token_returns_401(self, client):
        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 401


# ── RBAC / Protected Routes ───────────────────────────────────────────────────

class TestProtectedRoutes:
    def test_protected_route_requires_authentication(self, client):
        """Supplies list requires auth."""
        resp = client.get("/api/v1/supplies")
        assert resp.status_code == 401

    def test_protected_route_accepts_valid_token(self, client, active_admin):
        token = create_access_token(data={"sub": active_admin.username})
        resp = client.get(
            "/api/v1/supplies",
            headers={"Authorization": f"Bearer {token}"},
        )
        # 200 (no supplies) — authenticated access granted
        assert resp.status_code == 200

    def test_admin_can_access_audit_logs(self, client, active_admin):
        token = create_access_token(data={"sub": active_admin.username})
        resp = client.get(
            "/api/v1/audit-logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_non_admin_cannot_access_audit_logs(self, client, db_session):
        # Create pharmacist
        pharmacist = User(
            username="pharm",
            email="pharm@test.com",
            password_hash=hash_password("pass123"),
            full_name="Pharm User",
            role="Pharmacist",
            is_active=True,
        )
        db_session.add(pharmacist)
        db_session.commit()

        token = create_access_token(data={"sub": "pharm"})
        resp = client.get(
            "/api/v1/audit-logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
