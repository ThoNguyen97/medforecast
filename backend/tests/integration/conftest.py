"""
Shared fixtures for integration tests.

Each test module gets a fresh in-memory SQLite database and a TestClient
wired to that database through FastAPI's dependency injection system.
This ensures full isolation between tests.
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


# ── Database helpers ──────────────────────────────────────────────────────────

def build_test_engine():
    """Create a fresh in-memory SQLite engine."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


def build_session_factory(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def db_engine():
    """Provide a fresh engine (tables created) per test."""
    engine = build_test_engine()
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Provide a database session bound to the test engine."""
    SessionLocal = build_session_factory(db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Return a TestClient wired to the test DB session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ── User fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def admin_user(db_session):
    """Create and return an Administrator user."""
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
    """Create and return a Pharmacist user."""
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
def inventory_manager_user(db_session):
    """Create and return an Inventory_Manager user."""
    user = User(
        username="invmanager",
        email="invmanager@test.com",
        password_hash=hash_password("invpass123"),
        full_name="Inventory Manager",
        role="Inventory_Manager",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ── Token fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def admin_token(admin_user):
    return create_access_token(data={"sub": admin_user.username})


@pytest.fixture
def pharmacist_token(pharmacist_user):
    return create_access_token(data={"sub": pharmacist_user.username})


@pytest.fixture
def inventory_manager_token(inventory_manager_user):
    return create_access_token(data={"sub": inventory_manager_user.username})


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def pharmacist_headers(pharmacist_token):
    return {"Authorization": f"Bearer {pharmacist_token}"}


@pytest.fixture
def inventory_manager_headers(inventory_manager_token):
    return {"Authorization": f"Bearer {inventory_manager_token}"}
