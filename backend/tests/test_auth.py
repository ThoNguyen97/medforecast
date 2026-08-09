"""Tests for authentication endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import get_db, Base
from app.models.user import User
from app.core.security import hash_password

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture
def test_user():
    """Create a test user."""
    db = TestingSessionLocal()
    
    # Clean up existing test user
    existing_user = db.query(User).filter(User.username == "testuser").first()
    if existing_user:
        db.delete(existing_user)
        db.commit()
    
    # Create new test user
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=hash_password("testpass123"),
        full_name="Test User",
        role="Administrator",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def test_login_success(test_user):
    """Test successful login."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_username():
    """Test login with invalid username."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "nonexistent", "password": "testpass123"}
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_login_invalid_password(test_user):
    """Test login with invalid password."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_get_current_user(test_user):
    """Test getting current user info."""
    # First login to get token
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"}
    )
    token = login_response.json()["access_token"]
    
    # Get current user
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert data["role"] == "Administrator"


def test_get_current_user_invalid_token():
    """Test getting current user with invalid token."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401


def test_refresh_token(test_user):
    """Test token refresh."""
    # First login to get token
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"}
    )
    token = login_response.json()["access_token"]
    
    # Refresh token
    response = client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    # New token should be valid (might be same if generated at same time)
    assert len(data["access_token"]) > 0


def test_logout(test_user):
    """Test logout."""
    # First login to get token
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"}
    )
    token = login_response.json()["access_token"]
    
    # Logout
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"


def test_protected_endpoint_without_token():
    """Test accessing protected endpoint without token."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401  # No Authorization header


def test_inactive_user():
    """Test login with inactive user."""
    db = TestingSessionLocal()
    
    # Create inactive user
    inactive_user = User(
        username="inactive",
        email="inactive@example.com",
        password_hash=hash_password("testpass123"),
        full_name="Inactive User",
        role="Administrator",
        is_active=False
    )
    db.add(inactive_user)
    db.commit()
    
    # Try to login
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "inactive", "password": "testpass123"}
    )
    assert response.status_code == 400
    assert "Inactive user" in response.json()["detail"]
    
    # Clean up
    db.delete(inactive_user)
    db.commit()
    db.close()